package main

import (
	"errors"
	"sync"
	"testing"

	"stzbHelper/global"

	"github.com/google/gopacket/pcap"
)

func TestRunNpcapWithDepsReturnsErrorWhenDeviceListFails(t *testing.T) {
	captureCalled := false

	err := runNpcapWithDeps(
		func() ([]pcap.Interface, error) {
			return nil, errors.New("pcap unavailable")
		},
		func(string, *sync.WaitGroup) {
			captureCalled = true
		},
		func() {},
	)
	if err == nil {
		t.Fatal("runNpcapWithDeps error = nil, want device list error")
	}
	if captureCalled {
		t.Fatal("capture starter was called when device discovery failed")
	}
}

func TestRunNpcapWithDepsReturnsErrorWhenNoDevicesFound(t *testing.T) {
	captureCalled := false

	err := runNpcapWithDeps(
		func() ([]pcap.Interface, error) {
			return []pcap.Interface{}, nil
		},
		func(string, *sync.WaitGroup) {
			captureCalled = true
		},
		func() {},
	)
	if err == nil {
		t.Fatal("runNpcapWithDeps error = nil, want no devices error")
	}
	if captureCalled {
		t.Fatal("capture starter was called when no devices exist")
	}
}

func TestAutoBindDatabaseFromBookDataReturnsErrorOnBadJSON(t *testing.T) {
	databaseSelected = false
	globalOnlySrc := global.OnlySrcIp
	globalOnlyDst := global.OnlyDstIp
	defer func() {
		global.OnlySrcIp = globalOnlySrc
		global.OnlyDstIp = globalOnlyDst
		databaseSelected = false
	}()

	err := autoBindDatabaseFromBookData([]byte("not-json"), "127.0.0.1:9000", "127.0.0.1:8001")
	if err == nil {
		t.Fatal("autoBindDatabaseFromBookData error = nil, want bad json error")
	}
	if databaseSelected {
		t.Fatal("databaseSelected = true, want false on bad json")
	}
}
