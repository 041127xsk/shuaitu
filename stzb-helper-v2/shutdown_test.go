package main

import (
	"testing"
)

// stopAllCapture 必须幂等：Wails 的 OnBeforeClose 与 OnShutdown 可能都会调用，
// 重复调用不能 panic（重复关闭同一句柄会出问题）。
func TestStopAllCaptureIdempotent(t *testing.T) {
	stopAllCapture()
	stopAllCapture()
	stopAllCapture()

	captureHandlesMu.Lock()
	stopped := captureStopped
	remaining := len(captureHandles)
	captureHandlesMu.Unlock()

	if !stopped {
		t.Fatal("调用 stopAllCapture 后 captureStopped 应为 true")
	}
	if remaining != 0 {
		t.Fatalf("stopAllCapture 后注册表应清空，实际还有 %d 个", remaining)
	}
}

// 退出流程开始后，captureStopped 必须为 true，
// 这样后续 registerCaptureHandle 会走「立即关闭」分支，而不是继续挂起新线程。
func TestCaptureStoppedFlagSetAfterStop(t *testing.T) {
	stopAllCapture()
	captureHandlesMu.Lock()
	stopped := captureStopped
	captureHandlesMu.Unlock()
	if !stopped {
		t.Fatal("stopAllCapture 后 captureStopped 必须为 true，否则退出时会继续挂起新线程")
	}
}
