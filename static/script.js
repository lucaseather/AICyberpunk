document.addEventListener('DOMContentLoaded', function() {
    const searchForm = document.getElementById('searchForm');
    const wordInput = document.getElementById('wordInput');
    const resultDiv = document.getElementById('result');
    const wordDisplay = document.getElementById('word');
    const translationDisplay = document.getElementById('translation');
    const playBtn = document.getElementById('playBtn');
    const historyList = document.getElementById('historyList');

    let currentAudio = null;

    // 加载历史记录
    loadHistory();

    // 搜索表单提交
    searchForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        const word = wordInput.value.trim();
        if (!word) return;

        try {
            const response = await fetch('/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded',
                },
                body: `word=${encodeURIComponent(word)}`
            });

            const data = await response.json();
            if (data.error) {
                alert(data.error);
                return;
            }

            // 显示结果
            wordDisplay.textContent = data.word;
            translationDisplay.textContent = data.translation;
            resultDiv.classList.remove('d-none');

            // 设置音频
            if (currentAudio) {
                currentAudio.pause();
            }
            currentAudio = new Audio(data.audio_url);
            currentAudio.onended = () => {
                playBtn.classList.remove('playing');
            };

            // 重新加载历史记录
            loadHistory();
        } catch (error) {
            console.error('Error:', error);
            alert('搜索失败，请稍后重试');
        }
    });

    // 播放按钮点击
    playBtn.addEventListener('click', function() {
        if (currentAudio) {
            if (currentAudio.paused) {
                currentAudio.play();
                playBtn.classList.add('playing');
            } else {
                currentAudio.pause();
                playBtn.classList.remove('playing');
            }
        }
    });

    // 加载历史记录
    async function loadHistory() {
        try {
            const response = await fetch('/history');
            const history = await response.json();
            
            historyList.innerHTML = history.map(item => `
                <div class="list-group-item">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <strong>${item.word}</strong>
                            <p class="mb-0">${item.translation}</p>
                            <small class="text-muted">${item.timestamp}</small>
                        </div>
                        <button class="btn cyberpunk-btn-sm" onclick="searchWord('${item.word}')">
                            重新搜索
                        </button>
                    </div>
                </div>
            `).join('');
        } catch (error) {
            console.error('Error loading history:', error);
        }
    }

    // 点击历史记录中的单词
    window.searchWord = function(word) {
        wordInput.value = word;
        searchForm.dispatchEvent(new Event('submit'));
    };
}); 