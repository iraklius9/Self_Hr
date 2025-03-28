document.addEventListener('DOMContentLoaded', function() {
    // Check for new notifications every minute
    setInterval(function() {
        fetch('/notifications/check/')
            .then(response => response.json())
            .then(data => {
                if (data.count > 0) {
                    const badge = document.getElementById('notification-badge');
                    if (badge) {
                        badge.textContent = data.count;
                        badge.classList.remove('d-none');
                    }
                }
            })
            .catch(error => {
                console.error('Error checking notifications:', error);
            });
    }, 60000);

    // Mark notifications as read when clicked
    const notificationItems = document.querySelectorAll('.notification-item');
    notificationItems.forEach(item => {
        item.addEventListener('click', function(e) {
            const notificationId = this.dataset.notificationId;
            if (notificationId) {
                fetch(`/notifications/mark-read/${notificationId}/`, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': getCookie('csrftoken'),
                        'Content-Type': 'application/json'
                    }
                })
                .then(response => response.json())
                .then(data => {
                    if (data.status === 'success') {
                        this.classList.remove('unread');
                        this.classList.add('read');
                        
                        // Update notification count
                        const badge = document.getElementById('notification-badge');
                        if (badge) {
                            const count = parseInt(badge.textContent) - 1;
                            if (count > 0) {
                                badge.textContent = count;
                            } else {
                                badge.classList.add('d-none');
                            }
                        }
                    }
                });
            }
        });
    });

    // Helper function to get CSRF token from cookies
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }
}); 