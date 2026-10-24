package main

import (
	"context"
	"embed"
	"io"
	"log"
	"os"
	"stzbHelper/global"

	"github.com/wailsapp/wails/v2"
	"github.com/wailsapp/wails/v2/pkg/options"
	"github.com/wailsapp/wails/v2/pkg/options/assetserver"
)

//go:embed all:frontend/dist
var assets embed.FS

func main() {
	logFile, _ := os.CreateTemp("", "stzb-helper-*.log")
	if logFile != nil {
		log.SetOutput(io.MultiWriter(global.LogW, logFile))
		log.Printf("日志文件: %s", logFile.Name())
	} else {
		log.SetOutput(global.LogW)
	}

	// 禁用 WebView2 GPU 硬件加速：双显卡笔记本（RTX 3060 + Iris Xe）下
	// 渲染进程易崩溃（WebView2 process crashed），改用 CPU 渲染提升稳定性
	// 追加 --disable-gpu-sandbox 与 VizDisplayCompositor 进一步规避崩溃
	if os.Getenv("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS") == "" {
		os.Setenv("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS",
			"--disable-gpu --disable-gpu-sandbox --disable-features=VizDisplayCompositor")
		log.Printf("已禁用 WebView2 GPU 硬件加速并关闭 GPU 沙箱（双显卡稳定性优化）")
	}

	go runNpcap()
	// Create an instance of the app structure
	app := NewApp()

	// Create application with options
	err := wails.Run(&options.App{
		Title:     "stzbHelper",
		Width:     1600,
		Height:    900,
		Frameless: true,
		AssetServer: &assetserver.Options{
			Assets: assets,
		},
		BackgroundColour: &options.RGBA{R: 255, G: 255, B: 255, A: 1},
		OnStartup:        app.startup,
		// 退出前主动关闭抓包句柄。抓包 goroutine 阻塞在 pcap.BlockForever 的读取上，
		// 不主动关闭的话 Quit() 之后进程无法干净退出（窗口消失但进程残留）。
		OnBeforeClose: func(ctx context.Context) bool {
			log.Printf("收到关闭请求，正在停止抓包…")
			stopAllCapture()
			return false // 返回 false 表示允许关闭，不阻止退出
		},
		OnShutdown: func(ctx context.Context) {
			// 兜底：即使 OnBeforeClose 没有覆盖到，也在退出时再关一次（stopAllCapture 幂等）
			stopAllCapture()
		},
		Bind: []interface{}{
			app,
		},
	})

	if err != nil {
		println("Error:", err.Error())
	}
}
