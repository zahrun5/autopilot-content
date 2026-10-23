#!/data/data/com.termux/files/usr/bin/bash
# Launcher bot Telegram autopilot-content (via tmux, supaya survive terminal close)
# Pakai: ./run_bot.sh {start|stop|restart|status|log|attach}

DIR="$(cd "$(dirname "$0")" && pwd)"
SESSION="autopilot_bot"
LOG="$DIR/bot.log"

cd "$DIR" || exit 1

is_running() {
    tmux has-session -t "$SESSION" 2>/dev/null
}

start() {
    if is_running; then
        echo "Bot sudah jalan (tmux session: $SESSION)"
        return
    fi
    tmux new-session -d -s "$SESSION" \
        "cd '$DIR' && python -u src/bot.py 2>&1 | tee -a '$LOG'"
    sleep 3
    if is_running; then
        echo "Bot started (tmux session: $SESSION)"
        echo "Lihat log : ./run_bot.sh log"
        echo "Lihat terminal : ./run_bot.sh attach"
    else
        echo "Gagal start. Cek: $LOG"
    fi
}

stop() {
    if is_running; then
        tmux kill-session -t "$SESSION" 2>/dev/null
        echo "Bot stopped"
    else
        pkill -f "src/bot.py" 2>/dev/null
        echo "Bot tidak running"
    fi
}

case "$1" in
    start)   start ;;
    stop)    stop ;;
    restart) stop; sleep 1; start ;;
    status)  is_running && echo "Running (tmux session: $SESSION)" || echo "Not running" ;;
    log)     tail -f "$LOG" ;;
    attach)  tmux attach -t "$SESSION" ;;
    *)       echo "Pakai: $0 {start|stop|restart|status|log|attach}"; exit 1 ;;
esac
