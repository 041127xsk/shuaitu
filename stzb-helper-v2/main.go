package main

import (
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
		Bind: []interface{}{
			app,
		},
	})

	if err != nil {
		println("Error:", err.Error())
	}
}
