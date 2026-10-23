#!/data/data/com.termux/files/usr/bin/bash
# Launcher bot Telegram autopilot-content
# Pakai: ./run_bot.sh [start|stop|restart|status|log]

DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$DIR/.bot.pid"
LOG="$DIR/bot.log"
CMD="python src/bot.py"

cd "$DIR" || exit 1

is_running() {
    [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null
}

start() {
    if is_running; then
        echo "Bot sudah jalan (PID $(cat "$PIDFILE"))"
        return
    fi
    setsid nohup $CMD > "$LOG" 2>&1 < /dev/null &
    echo $! > "$PIDFILE"
    sleep 3
    if is_running; then
        echo "Bot started (PID $(cat "$PIDFILE"))"
    else
        echo "Gagal start. Cek: $LOG"
    fi
}

stop() {
    if is_running; then
        kill "$(cat "$PIDFILE")" 2>/dev/null
        sleep 2
        kill -9 "$(cat "$PIDFILE")" 2>/dev/null
        echo "Bot stopped"
    else
        pkill -f "src/bot.py" 2>/dev/null
        echo "Bot tidak running"
    fi
    rm -f "$PIDFILE"
}

case "$1" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; sleep 1; start ;;
    status)  is_running && echo "Running (PID $(cat "$PIDFILE"))" || echo "Not running" ;;
    log)     tail -f "$LOG" ;;
    *)       echo "Pakai: $0 {start|stop|restart|status|log}"; exit 1 ;;
esac
