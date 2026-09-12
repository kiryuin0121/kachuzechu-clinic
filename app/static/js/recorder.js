/**
 * 録音・採点処理（practice.html用）
 *
 *【3つのステップ】
 * 1. 「開始」ボタン → getUserMedia でマイク許可を取得 → MediaRecorder で録音開始
 * 2. 「停止」ボタン → 録音を止める → 音声 + お題ID + 時間を /practice/score へ POST
 * 3. サーバーから JSON（スコア・認識結果・差分）を受け取る → 画面に表示
 *
 * 【送るデータ】
 * - audio : 音声 Blob（形式はブラウザが決める）
 * - tongue_twister_id : お題ID
 * - duration_seconds : 時間（フロントで計測）
 *   → サーバー側でもバリデーション必須（クライアントは改ざん可能）
 */

(() => {
    const recorderElement = document.getElementById("recorder");
    if (!recorderElement) {
        return; // 練習画面以外では何もしない
    }

    const tongueTwisterId = recorderElement.dataset.tongueTwisterId;
    const scoreEndpoint = recorderElement.dataset.scoreEndpoint;

    const startButton = document.getElementById("start-button");
    const stopButton = document.getElementById("stop-button");
    const timerDisplay = document.getElementById("recording-timer");
    const statusText = document.getElementById("scoring-status");

    const resultSection = document.getElementById("result-section");
    const resultTotalScore = document.getElementById("result-total-score");
    const resultAccuracyScore = document.getElementById("result-accuracy-score");
    const resultSpeedScore = document.getElementById("result-speed-score");
    const resultDuration = document.getElementById("result-duration");
    const resultTargetDuration = document.getElementById("result-target-duration");
    const resultRepeatCount = document.getElementById("result-repeat-count");
    const resultTranscribedText = document.getElementById("result-transcribed-text");
    const resultDiff = document.getElementById("result-diff");
    const resultLogMessage = document.getElementById("result-log-message");
    const latestAudioPlayer = document.getElementById("latest-audio");

    let mediaRecorder = null;
    let recordedChunks = [];
    let recordingStartedAt = 0;
    let timerIntervalId = null;

    function setStatus(message) {
        statusText.textContent = message;
    }

    function updateTimerDisplay() {
        const elapsedSeconds = (Date.now() - recordingStartedAt) / 1000;
        timerDisplay.textContent = elapsedSeconds.toFixed(1);
    }

    // ブラウザが MediaRecorder と getUserMedia に対応しているかチェック
    const isSupported = typeof window.MediaRecorder !== "undefined" && navigator.mediaDevices;
    if (!isSupported) {
        startButton.disabled = true;
        setStatus("このブラウザは録音機能に対応していません。");
    }

    startButton.addEventListener("click", async () => {
        resultSection.hidden = true;
        setStatus("");

        try {
            // マイクを開く
            const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            recordedChunks = [];

            // 録音開始
            mediaRecorder = new MediaRecorder(stream);
            mediaRecorder.addEventListener("dataavailable", (e) => {
                if (e.data.size > 0) recordedChunks.push(e.data);
            });

            mediaRecorder.addEventListener("stop", () => {
                stream.getTracks().forEach((t) => t.stop());
                const duration = (Date.now() - recordingStartedAt) / 1000;
                const mimeType = mediaRecorder.mimeType?.split(";")[0] || "audio/webm";
                const audioBlob = new Blob(recordedChunks, { type: mimeType });
                submitRecording(audioBlob, duration);
            });

            mediaRecorder.start();
            recordingStartedAt = Date.now();
            timerDisplay.textContent = "0.0";
            timerIntervalId = window.setInterval(updateTimerDisplay, 100);

            startButton.disabled = true;
            stopButton.disabled = false;
            setStatus("録音中です。お題を3回連続で読み上げてください。");
        } catch (error) {
            setStatus("マイクを使用できませんでした。ブラウザの設定を確認してください。");
        }
    });

    stopButton.addEventListener("click", () => {
        if (mediaRecorder?.state !== "inactive") {
            mediaRecorder.stop();
        }
        window.clearInterval(timerIntervalId);
        startButton.disabled = false;
        stopButton.disabled = true;
    });

    async function submitRecording(audioBlob, durationSeconds, recordedMimeType) {
        if (!audioBlob?.size) {
            setStatus("録音データが取得できませんでした。");
            return;
        }

        setStatus("音声を送信し、採点を行っています…");

        const formData = new FormData();
        formData.append("audio", audioBlob, "recording.webm");
        formData.append("tongue_twister_id", tongueTwisterId);
        formData.append("duration_seconds", durationSeconds.toFixed(2));

        try {
            const response = await fetch(scoreEndpoint, {
                method: "POST",
                body: formData,
            });
            const payload = await response.json();

            if (!payload.success) {
                setStatus(payload.message || "採点に失敗しました。");
                return;
            }

            renderResult(payload);
        } catch {
            setStatus("通信エラーが発生しました。");
        }
    }

    function renderResult(result) {
        resultTotalScore.textContent = `${result.total_score}点`;
        resultAccuracyScore.textContent = `${result.accuracy_score}点`;
        resultSpeedScore.textContent = `${result.speed_score}点`;
        resultDuration.textContent = result.duration_seconds.toFixed(1);
        resultTargetDuration.textContent = result.target_duration.toFixed(1);
        resultRepeatCount.textContent = result.repeat_count;
        resultTranscribedText.textContent = result.transcribed_text;

        // 差分表示（正解と認識結果を色分け）
        resultDiff.innerHTML = "";
        (result.diff || []).forEach(({ type, expected, actual }) => {
            const span = document.createElement("span");
            if (type === "equal") {
                span.textContent = expected;
                span.className = "text-green-600";
            } else if (type === "replace") {
                span.innerHTML = `<span class="line-through text-orange-500">${expected}</span><span class="text-orange-600">(${actual})</span>`;
            } else if (type === "delete") {
                span.textContent = expected;
                span.className = "line-through text-red-500";
            } else if (type === "insert") {
                span.textContent = actual;
                span.className = "text-blue-600 underline";
            }
            resultDiff.appendChild(span);
        });

        // 保存状況の表示
        if (result.log_saved === false && result.log_save_error) {
            resultLogMessage.textContent = result.log_save_error;
        } else if (result.log_saved) {
            resultLogMessage.textContent = "この結果は練習履歴として保存されました。";
        } else {
            resultLogMessage.textContent = "ゲストとして練習したため、結果は保存されません。";
        }

        resultSection.hidden = false;

        // 会員の場合、音声プレイヤーをリロード（キャッシュ回避）
        if (latestAudioPlayer && result.log_saved) {
            const baseUrl = latestAudioPlayer.src.split("?")[0];
            latestAudioPlayer.src = `${baseUrl}?t=${Date.now()}`;
        }
    }
})();
