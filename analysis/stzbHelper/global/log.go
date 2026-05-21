package global

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/wailsapp/wails/v2/pkg/runtime"
)

const maxLogEntries = 1000

var LogW = &LogWriter{}

type LogWriter struct {
	ctx     context.Context
	mu      sync.RWMutex
	entries []string
}

func (w *LogWriter) SetContext(ctx context.Context) {
	w.ctx = ctx
}

func (w *LogWriter) Write(p []byte) (n int, err error) {
	msg := string(p)
	ts := time.Now().Format("2006-01-02 15:04:05")
	line := fmt.Sprintf("[%s] %s", ts, msg)

	w.mu.Lock()
	w.entries = append(w.entries, line)
	if len(w.entries) > maxLogEntries {
		w.entries = w.entries[len(w.entries)-maxLogEntries:]
	}
	w.mu.Unlock()

	if w.ctx != nil {
		runtime.EventsEmit(w.ctx, "log", line)
	}

	return len(p), nil
}

func (w *LogWriter) GetLogs() []string {
	w.mu.RLock()
	defer w.mu.RUnlock()
	result := make([]string, len(w.entries))
	copy(result, w.entries)
	return result
}

func (w *LogWriter) Clear() {
	w.mu.Lock()
	w.entries = nil
	w.mu.Unlock()
}
