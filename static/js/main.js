const socket = io();

socket.on('log', function(data) {
    const logs = document.getElementById('logs');
    const log = document.createElement('p');
    log.textContent = data.message;
    log.className = data.level === 'ERROR' ? 'text-danger' : 'text-info';
    logs.appendChild(log);
    logs.scrollTop = logs.scrollHeight;
});

socket.on('notification', function(data) {
    const toastTemplate = document.getElementById('toast-template');
    const toast = toastTemplate.cloneNode(true);
    toast.classList.add(`bg-${data.type || 'info'}`);
    toast.querySelector('.toast-body').textContent = data.message;
    document.querySelector('.toast-container').appendChild(toast);
    new bootstrap.Toast(toast, { autohide: true, delay: 5000 }).show();
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
});

socket.on('status_update', function(data) {
    console.log('Получено status_update:', data);
    const row = document.querySelector(`tr[data-url="${data.series_url}"]`);
    if (row) {
        const statusCell = row.querySelector('.status');
        const actionButtons = row.querySelectorAll('.actions .btn');
        row.classList.remove('bg-warning', 'bg-success', 'bg-danger');

        if (data.status === 'Завершено') {
            row.classList.add('bg-success');
            statusCell.textContent = 'Готов';
            actionButtons.forEach(btn => btn.removeAttribute('disabled'));
        } else if (data.status.startsWith('Ошибка')) {
            row.classList.add('bg-danger');
            statusCell.textContent = data.status;
            actionButtons.forEach(btn => btn.removeAttribute('disabled'));
        } else {
            row.classList.add('bg-warning');
            statusCell.textContent = data.total > 0 ? `${data.progress}/${data.total}` : data.status;
            actionButtons.forEach(btn => btn.setAttribute('disabled', 'disabled'));
        }
        console.log(`Обновлена строка ${data.series_url}: статус=${statusCell.textContent}, класс=${row.className}`);
        const firstCell = row.querySelector('td');
        console.log(`Стиль первой ячейки: background-color=${getComputedStyle(firstCell).backgroundColor}`);
    } else {
        console.log(`Строка для ${data.series_url} не найдена`);
    }
});

document.querySelectorAll('.delete-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        window.location.href = `/delete/${this.dataset.url}`;
    });
});

document.querySelectorAll('.status-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        const seriesUrl = this.dataset.url;
        fetch(`/api/status/${seriesUrl}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    document.getElementById('status-content').innerHTML = `<p class="text-danger">${data.error}</p>`;
                } else {
                    let html = `<p>Всего: ${data.total}</p><p>Скачано: <span class="text-success">${data.downloaded}</span></p><p>Новых: <span class="text-primary">${data.new}</span></p>`;
                    html += '<table class="table"><thead><tr><th>Название</th><th>Дата</th><th>ID</th><th>Статус</th></tr></thead><tbody>';
                    data.episodes.forEach(ep => {
                        html += `<tr><td>${ep.name}</td><td>${ep.date}</td><td>${ep.torrent_id}</td><td class="${ep.status === 'Скачан/В загрузках' ? 'text-success' : 'text-primary'}">${ep.status}</td></tr>`;
                    });
                    html += '</tbody></table>';
                    document.getElementById('status-content').innerHTML = html;
                }
                new bootstrap.Modal(document.getElementById('statusModal')).show();
            });
    });
});

document.querySelectorAll('.scan-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        window.location.href = `/scan_series/${this.dataset.url}`;
    });
});

document.querySelectorAll('.rename-btn').forEach(btn => {
    btn.addEventListener('click', function() {
        const seriesUrl = this.dataset.url;
        fetch(`/api/rename/${seriesUrl}`)
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    document.getElementById('rename-preview').innerHTML = `<p class="text-danger">${data.error}</p>`;
                } else {
                    document.getElementById('rename-series-name').value = data.series_data.series_name;
                    document.getElementById('rename-season').value = data.series_data.season;
                    let html = '<h6>Предпросмотр</h6><table class="table"><thead><tr><th>Текущее имя</th><th>Новое имя</th></tr></thead><tbody>';
                    data.rename_preview.forEach(item => {
                        html += `<tr><td>${item.current_name}</td><td>${item.new_name}</td></tr>`;
                    });
                    html += '</tbody></table>';
                    document.getElementById('rename-preview').innerHTML = html;
                }
                const modal = new bootstrap.Modal(document.getElementById('renameModal'));
                modal.show();
                document.getElementById('rename-form').dataset.url = seriesUrl;
            });
    });
});

document.getElementById('rename-form').addEventListener('submit', function(e) {
    e.preventDefault();
    const seriesUrl = this.dataset.url;
    const formData = new FormData(this);
    fetch(`/api/rename/${seriesUrl}`, {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(data.message, 'success');
                bootstrap.Modal.getInstance(document.getElementById('renameModal')).hide(); // Закрываем модальное окно
            }
        })
        .catch(error => {
            console.error('Ошибка при отправке запроса:', error);
            showToast('Произошла ошибка при переименовании', 'danger');
        });
});

document.querySelectorAll('.rename-toggle').forEach(toggle => {
    toggle.addEventListener('change', function() {
        const seriesUrl = this.dataset.url;
        fetch(`/api/toggle_rename/${seriesUrl}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: this.checked })
        });
    });
});

// Функция для отображения toast-уведомлений
function showToast(message, type) {
    const toastTemplate = document.getElementById('toast-template');
    const toast = toastTemplate.cloneNode(true);
    toast.classList.add(`bg-${type || 'info'}`);
    toast.querySelector('.toast-body').textContent = message;
    document.querySelector('.toast-container').appendChild(toast);
    new bootstrap.Toast(toast, { autohide: true, delay: 5000 }).show();
    toast.addEventListener('hidden.bs.toast', () => toast.remove());
}