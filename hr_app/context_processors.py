from .models import Notification

def unread_notifications(request):
    if request.user.is_authenticated:
        return {
            'unread_notifications': Notification.objects.filter(
                user=request.user, 
                read=False
            ).order_by('-created_at')[:5]
        }
    return {'unread_notifications': []}

def common_data(request):
    if request.user.is_authenticated:
        return {
            'is_at_workplace': request.session.get('is_at_workplace', False),
            'current_ip': request.session.get('current_ip', ''),
            'unread_notifications_count': request.user.notifications.filter(read=False).count(),
        }
    return {} 