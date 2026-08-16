package main

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"github.com/google/gopacket"
	"github.com/google/gopacket/layers"
	"github.com/google/gopacket/pcap"
	"log"
	"strconv"
	"strings"
	"stzbHelper/global"
	"stzbHelper/model"
	"sync"
	"time"
)

var databaseSelected bool = false

// captureState 每个抓包接口独立的分包重组状态。
// 旧实现使用全局变量（fullbuf/waitbuf/LossBytes/PacketLoss），
// 多网卡并发抓包时会互相污染，导致 TCP 分包重组错乱、战报丢失。
type captureState struct {
	bufMu       sync.Mutex
	fullbuf     []byte
	fullsize    int
	waitbuf     bool
	packetLoss  bool
	lossBytes   []byte
	lossCmdId   int
	needBufSize int

	// 统计计数（可观测性：漏采定位）
	packetsTotal int64 // 收到的 TCP 载荷包总数（payload>=8）
	packetsDrop  int64 // 被丢弃的包数（解析失败/无法处理）
	packetsParse int64 // 成功进入 ParseData 的包数
	bufWaits     int64 // 等待分包闭合的次数（非 PSH 开头）
	bufTimeouts  int64 // 分包等待超时被丢弃的次数
	lossDetected int64 // 检测到丢包（进入 loss 拼接）的次数
	lossResolved int64 // 丢包拼接成功的次数

	// 分包等待超时（毫秒）：超过该时间未等到闭合 PSH 则丢弃缓冲，避免永久挂起
	bufWaitStart time.Time
	bufWaitLimit time.Duration
}

var initDBForAutoBind = model.InitDB

func runNpcap() {
	if err := runNpcapWithDeps(
		pcap.FindAllDevs,
		func(deviceName string, wg *sync.WaitGroup) {
			go captureTCPPackets(deviceName, wg)
		},
		func() {
			time.Sleep(100 * time.Millisecond)
		},
	); err != nil {
		log.Printf("Npcap 启动失败: %v", err)
	}
}

func runNpcapWithDeps(
	findAllDevs func() ([]pcap.Interface, error),
	startCapture func(string, *sync.WaitGroup),
	beforeCapture func(),
) error {
	devices, err := findAllDevs()
	if err != nil {
		return fmt.Errorf("无法获取网络接口列表: %w", err)
	}

	if len(devices) == 0 {
		return fmt.Errorf("未找到可用的网络接口")
	}

	if global.IsDebug == true {
		fmt.Println("可用的网络接口:")
		for i, device := range devices {
			fmt.Printf("%d: %s (%s)\n", i+1, device.Name, device.Description)
		}
	}

	var wg sync.WaitGroup

	log.Println("stzbHelper开始运行!")
	log.Println("version:", global.Version)

	if beforeCapture != nil {
		beforeCapture()
	}

	for _, device := range devices {
		wg.Add(1)
		startCapture(device.Name, &wg)
	}

	wg.Wait()
	return nil
}

func autoBindDatabaseFromBookData(data []byte, dstIP string, srcIP string) error {
	var raw []interface{}
	if err := json.Unmarshal(data, &raw); err != nil {
		return fmt.Errorf("解析主公簿数据失败: %w", err)
	}
	if len(raw) < 2 {
		return fmt.Errorf("主公簿数据格式异常: 根数组长度不足")
	}

	dataMap, ok := raw[1].(map[string]interface{})
	if !ok {
		return fmt.Errorf("主公簿数据格式异常: 第2项不是对象")
	}

	server, ok := dataMap["server"].([]interface{})
	if ok {
		log.Printf("服务器信息: %v\n", server)
	}

	logData, ok := dataMap["log"].(map[string]interface{})
	if !ok {
		return fmt.Errorf("主公簿数据格式异常: 缺少 log 信息")
	}
	roleName, ok := logData["role_name"].(string)
	if !ok || strings.TrimSpace(roleName) == "" {
		return fmt.Errorf("主公簿数据格式异常: 缺少角色名")
	}
	if len(server) == 0 {
		return fmt.Errorf("主公簿数据格式异常: 缺少服务器信息")
	}
	serverName, ok := server[0].(string)
	if !ok || strings.TrimSpace(serverName) == "" {
		return fmt.Errorf("主公簿数据格式异常: 服务器名为空")
	}

	log.Printf("角色名: %s\n", roleName)
	log.Println("本地IP：" + dstIP)
	log.Println("游戏服务器IP：" + srcIP)
	global.OnlySrcIp = srcIP
	global.OnlyDstIp = dstIP
	dabesename := roleName + "_" + serverName
	log.Println("收到主公簿数据，将打开数据库文件" + dabesename + ".db")
	initDBForAutoBind(dabesename)
	databaseSelected = true
	return nil
}

// captureTCPPackets 监听指定接口的 TCP 数据包
func captureTCPPackets(deviceName string, wg *sync.WaitGroup) {
	defer wg.Done()

	// 每个接口独立的抓包状态（避免多网卡并发污染全局缓冲）
	var st captureState

	// 打开网络接口
	handle, err := pcap.OpenLive(deviceName, 65535, true, pcap.BlockForever)
	if err != nil {
		log.Printf("无法打开接口 %s: %v\n", deviceName, err)
		return
	}
	defer handle.Close()

	// 设置过滤器，只捕获端口为 8001 的 TCP 数据包
	filter := "tcp and src port 8001"
	err = handle.SetBPFFilter(filter)
	if err != nil {
		log.Printf("无法在接口 %s 上设置过滤器: %v\n", deviceName, err)
		return
	}
	// 创建数据包源
	packetSource := gopacket.NewPacketSource(handle, handle.LinkType())

	// 循环读取数据包
	if global.IsDebug == true {
		fmt.Printf("开始在接口 %s 上捕获 TCP 数据包（端口 8001）...\n", deviceName)
	}

	// 定期输出抓包统计（每 60s），用于排查漏采
	go func() {
		ticker := time.NewTicker(60 * time.Second)
		defer ticker.Stop()
		for range ticker.C {
			st.bufMu.Lock()
			log.Printf("[抓包统计] 接口 %s: 总包=%d 解析=%d 丢弃=%d 分包等待=%d 分包超时=%d 丢包检测=%d 丢包恢复=%d 当前缓冲=%dB",
				deviceName, st.packetsTotal, st.packetsParse, st.packetsDrop,
				st.bufWaits, st.bufTimeouts, st.lossDetected, st.lossResolved, len(st.fullbuf))
			st.bufMu.Unlock()
		}
	}()

	for packet := range packetSource.Packets() {
		handlePacket(packet, &st)
	}
}

func handlePacket(packet gopacket.Packet, st *captureState) {
	if tcpLayer := packet.Layer(layers.LayerTypeTCP); tcpLayer != nil {
		if appLayer := packet.ApplicationLayer(); appLayer != nil {
			PSH := tcpLayer.(*layers.TCP).PSH
			payload := appLayer.Payload()
			if len(payload) < 8 {
				return
			}
			st.bufMu.Lock()
			st.packetsTotal++
			st.bufMu.Unlock()
			var srcIP string
			var dstIP string
			var srcProt int
			var dstProt int
			if ipLayer := packet.NetworkLayer(); ipLayer != nil {
				switch ip := ipLayer.(type) {
				case *layers.IPv4:
					srcProt = int(tcpLayer.(*layers.TCP).SrcPort)
					dstProt = int(tcpLayer.(*layers.TCP).DstPort)
					srcIP = ip.SrcIP.String() + ":" + strconv.Itoa(srcProt)
					dstIP = ip.DstIP.String() + ":" + strconv.Itoa(dstProt)
				case *layers.IPv6:
					srcProt = int(tcpLayer.(*layers.TCP).SrcPort)
					dstProt = int(tcpLayer.(*layers.TCP).DstPort)
					srcIP = ip.SrcIP.String() + ":" + strconv.Itoa(srcProt)
					dstIP = ip.DstIP.String() + ":" + strconv.Itoa(dstProt)
				}
			}

			if global.ExVar.BindIpInfo == true && global.OnlySrcIp != "" && global.OnlyDstIp != "" {
				if global.OnlySrcIp != srcIP || global.OnlyDstIp != dstIP {
					if global.IsDebug == true {
						fmt.Println("IP信息不符合跳过数据处理")
					}
					return
				}
			}

			var buf []byte
			if PSH != true {
				st.bufMu.Lock()
				st.bufWaits++
				if !st.waitbuf {
					// 新的分包等待开始，记录起始时间
					st.bufWaitStart = time.Now()
					st.bufWaitLimit = 5 * time.Second
				}
				st.waitbuf = true
				st.fullbuf = append(st.fullbuf, payload...)
				st.bufMu.Unlock()
				return
			} else {
				st.bufMu.Lock()
				if st.waitbuf == true {
					// 检查分包等待是否超时（超时说明中间分片丢失，丢弃缓冲防永久挂起）
					if time.Since(st.bufWaitStart) > st.bufWaitLimit {
						st.bufTimeouts++
						st.packetsDrop++
						log.Printf("[抓包] 接口分包重组超时(%v)，丢弃 %d 字节缓冲（可能是中间分片丢失）", st.bufWaitLimit, len(st.fullbuf))
						st.waitbuf = false
						st.fullbuf = []byte{}
					} else {
						st.waitbuf = false
						buf = append(st.fullbuf, payload...)
						st.fullbuf = []byte{}
					}
				} else {
					buf = payload
				}
				st.bufMu.Unlock()
			}

			if global.IsDebug == true {
				fmt.Println("")
				fmt.Println("====================================================")
				fmt.Println("")
			}
			bufread := NewBufferFrom(buf)
			bufsize := bufread.ReadInt()
			if global.IsDebug == true {
				fmt.Println("包大小", bufsize)
			}
			cmdId := bufread.ReadInt()
			if global.IsDebug == true {
				fmt.Println("协议号", cmdId)
			}

			if len(buf) > 14 {
				if global.IsDebug == true {
					fmt.Println("数据类型", buf[12])
				}

				if buf[12] == 3 {
					//fmt.Println(len(buf), bufsize, cmdId, "-----------")
					if len(buf)-bufsize != 4 && (cmdId == 103 || cmdId == 92) {
						st.lossCmdId = cmdId
						st.lossBytes = buf
						st.packetLoss = true
						st.needBufSize = bufsize
						st.bufMu.Lock()
						st.lossDetected++
						st.bufMu.Unlock()
					} else {
						st.bufMu.Lock()
						st.packetsParse++
						st.bufMu.Unlock()
						go ParseData(cmdId, buf[17:])
					}

				} else if buf[12] == 5 {
					//println(buf)
					if global.IsDebug == true {
						data := DecodeType5(buf[12:])
						fmt.Println(data)
					}
				} else if buf[12] == 2 {

					//if cmdId == 5028 || cmdId == 5026 {
					//	fmt.Println(string(buf[12:]))
					//}
					//
					//if cmdId == 5028 {
					//	Parse5028(buf[13:])
					//}
				} else if cmdId > 99999 && st.packetLoss == true && (st.lossCmdId == 103 || st.lossCmdId == 92) {
					result := make([]byte, len(buf)+len(st.lossBytes))
					copy(result, st.lossBytes)
					copy(result[len(st.lossBytes):], buf)
					if len(buf)+len(st.lossBytes)-st.needBufSize != 4 {
						st.lossBytes = result
					} else {
						st.packetLoss = false
						st.bufMu.Lock()
						st.lossResolved++
						st.packetsParse++
						st.bufMu.Unlock()
						go ParseData(st.lossCmdId, result[17:])
					}

				} else if buf[12] != 3 && buf[12] != 5 && buf[12] != 2 {
					// 无法识别的数据类型，计入丢弃
					st.bufMu.Lock()
					st.packetsDrop++
					st.bufMu.Unlock()
				}

				if cmdId == 3686 {
					var data []byte
					if buf[12] == 5 {
						data = []byte(DecodeType5(buf[12:]))
					} else if buf[12] == 3 {
						data = parseZlibData(buf[17:])
					}

					if global.ExVar.NeedPushBookData {
						go parseBookData(data)
					}

					if databaseSelected == false {
						if err := autoBindDatabaseFromBookData(data, dstIP, srcIP); err != nil {
							log.Printf("自动绑定数据库失败: %v", err)
						}
					}
				}
			}

			if global.IsDebug == true {
				fmt.Print("[]byte{")
				for i, b := range buf {
					if i > 0 {
						fmt.Print(", ")
					}
					fmt.Print(b)
				}
				fmt.Println("}")
				fmt.Println("")
				fmt.Println("====================================================")
				fmt.Println("")
			}
		}
	}
}

type Buffer struct {
	Byte   []byte
	pos    int
	offset int
}

func (bb *Buffer) ResetOffset() {
	bb.offset = 0
}

func NewBufferFrom(b []byte) *Buffer {
	return &Buffer{Byte: b}
}

func (bb *Buffer) ReadInt() int {
	if bb.offset+4 > len(bb.Byte) {
		return 0
	}
	value := binary.BigEndian.Uint32(bb.Byte[bb.offset : bb.offset+4])
	bb.offset += 4
	return int(value)
}

func (bb *Buffer) ReadByte() byte {
	if bb.offset+1 > len(bb.Byte) {
		return 0
	}
	value := bb.Byte[bb.offset : bb.offset+1]
	bb.offset += 1
	return value[0]
}
