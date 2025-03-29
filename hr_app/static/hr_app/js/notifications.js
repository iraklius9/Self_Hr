function checkNotifications() {
    fetch('/check-notifications/')
        .then(response => response.json())
        .then(data => {
            // Update notification count
            const countBadge = document.getElementById('notification-count');
            if (countBadge) {
                countBadge.textContent = data.unread_count;
                countBadge.style.display = data.unread_count > 0 ? 'inline' : 'none';
            }

            // Update notification list
            const notificationList = document.getElementById('notification-list');
            if (notificationList) {
                notificationList.innerHTML = '';
                data.notifications.forEach(notification => {
                    const li = document.createElement('li');
                    li.className = 'dropdown-item';
                    
                    if (notification.url) {
                        const a = document.createElement('a');
                        a.href = notification.url;
                        a.className = 'text-decoration-none text-dark';
                        a.textContent = notification.message;
                        li.appendChild(a);
                    } else {
                        li.textContent = notification.message;
                    }
                    
                    const small = document.createElement('small');
                    small.className = 'text-muted d-block';
                    small.textContent = notification.created_at;
                    li.appendChild(small);
                    
                    notificationList.appendChild(li);
                });
            }
        })
        .catch(error => console.error('Error checking notifications:', error));
}

// Check notifications every 30 seconds
setInterval(checkNotifications, 30000);

// Initial check
document.addEventListener('DOMContentLoaded', checkNotifications);

// Mark notification as read
function markAsRead(notificationId) {
    fetch(`/notifications/${notificationId}/mark-read/`, {
        method: 'POST',
        headers: {
            'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
        },
    })
    .then(response => response.json())
    .then(data => {
        if (data.status === 'success') {
            checkNotifications();
        }
    })
    .catch(error => console.error('Error marking notification as read:', error));
} 