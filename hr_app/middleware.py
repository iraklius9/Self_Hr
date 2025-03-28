from ipaddress import ip_network, ip_address
from django.conf import settings
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

class LocationTrackingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.geolocator = Nominatim(user_agent="hr_system")

    def __call__(self, request):
        if request.user.is_authenticated:
            # Get client IP
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')

            # Check if IP is in workplace range
            is_workplace_ip = any(
                ip_address(ip) in ip_network(network)
                for network in settings.WORKPLACE_IP_RANGES
            )

            # Get location from IP
            try:
                location = self.geolocator.geocode(ip)
                if location:
                    workplace = (settings.WORKPLACE_LATITUDE, settings.WORKPLACE_LONGITUDE)
                    current = (location.latitude, location.longitude)
                    distance = geodesic(workplace, current).km
                    is_at_workplace = distance <= settings.WORKPLACE_RADIUS_KM
                else:
                    is_at_workplace = is_workplace_ip
            except:
                is_at_workplace = is_workplace_ip

            request.session['is_at_workplace'] = is_at_workplace
            request.session['current_ip'] = ip

        response = self.get_response(request)
        return response 