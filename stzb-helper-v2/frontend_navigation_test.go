package main

import (
	"os"
	"strings"
	"testing"
)

func TestSidebarExposesAutoScrollPageWithRoute(t *testing.T) {
	appVue, err := os.ReadFile("frontend/src/App.vue")
	if err != nil {
		t.Fatalf("read App.vue: %v", err)
	}
	routesFile, err := os.ReadFile("frontend/src/routes.ts")
	if err != nil {
		t.Fatalf("read routes.ts: %v", err)
	}

	appContent := string(appVue)
	if !strings.Contains(appContent, "label: '自动翻页'") {
		t.Fatal("sidebar should expose the auto-scroll page entry")
	}
	if !strings.Contains(appContent, "key: 'autoscroll'") {
		t.Fatal("sidebar should include the auto-scroll route key")
	}

	routesContent := string(routesFile)
	if !strings.Contains(routesContent, "path: '/autoscroll'") {
		t.Fatal("routes should register the auto-scroll page")
	}
	if !strings.Contains(routesContent, "component: AutoScroll") {
		t.Fatal("routes should map /autoscroll to AutoScroll")
	}
}
