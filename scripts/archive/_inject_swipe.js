// Frida 触摸注入脚本：在 Unity 游戏内模拟滑动
// 用法: frida -U -n com.netease.stzb.uc -l _inject_swipe.js

function injectSwipe(startX, startY, endX, endY, durationMs) {
    Java.perform(function () {
        var MotionEvent = Java.use('android.view.MotionEvent');
        var SystemClock = Java.use('android.os.SystemClock');
        
        var now = SystemClock.uptimeMillis.value;
        
        // DOWN
        var downEvent = MotionEvent.obtain(
            now, now, 0, startX, startY, 0
        );
        
        // 获取当前 Activity 的 Window 注入事件
        var currentActivity = Java.use('android.app.ActivityThread').currentApplication().value;
        var windowManager = currentActivity.getSystemService('window');
        
        // 通过 InputManager 注入
        var InputManager = Java.use('android.hardware.input.InputManager');
        var im = InputManager.getInstance();
        
        // 用 Instrumentation 注入（需要系统权限或已 root）
        var Instrumentation = Java.use('android.app.Instrumentation');
        var inst = Instrumentation.$new();
        
        inst.sendPointerSync(downEvent);
        
        // MOVE (模拟中间点)
        var steps = 10;
        for (var i = 1; i <= steps; i++) {
            var progress = i / steps;
            var mx = startX + (endX - startX) * progress;
            var my = startY + (endY - startY) * progress;
            var moveEvent = MotionEvent.obtain(
                now, now + (durationMs * progress), 2, mx, my, 0
            );
            inst.sendPointerSync(moveEvent);
        }
        
        // UP
        var upEvent = MotionEvent.obtain(
            now, now + durationMs, 1, endX, endY, 0
        );
        inst.sendPointerSync(upEvent);
        
        console.log('[Swipe] Injected: (' + startX + ',' + startY + ') -> (' + endX + ',' + endY + ')');
    });
}

rpc.exports = {
    swipe: function(sx, sy, ex, ey, dur) {
        injectSwipe(sx, sy, ex, ey, dur || 400);
    }
};

console.log('[Touch Injector] Loaded. Use rpc.exports.swipe(x1,y1,x2,y2,dur)');
