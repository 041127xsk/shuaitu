package main

import (
	"os"
	"strings"
	"testing"
)

func TestSidebarDoesNotExposeAutoScrollPage(t *testing.T) {
	appVue, err := os.ReadFile("frontend/src/App.vue")
	if err != nil {
		t.Fatalf("read App.vue: %v", err)
	}

	content := string(appVue)
	if strings.Contains(content, "label: '自动翻页'") {
		t.Fatal("sidebar should not expose the blank auto-scroll page")
	}
	if strings.Contains(content, "key: 'autoscroll'") {
		t.Fatal("sidebar should not include the auto-scroll route key")
	}
}
