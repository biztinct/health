from . import models
from . import controllers

def post_init_hook(env):
    """Post-installation setup"""
    # Create default service types with appointment booking if they don't exist
    ServiceType = env['health.service.type']
    
    default_types = [
        {
            'name': 'General Consultation',
            'code': 'CONSULT',
            'duration_minutes': 30,
            'location_type': 'clinic',
            'color': 1,
            'active': True,
        },
        {
            'name': 'Home Visit',
            'code': 'HOME',
            'duration_minutes': 45,
            'location_type': 'home',
            'color': 3,
            'active': True,
        },
        {
            'name': 'Telemedicine',
            'code': 'TELE',
            'duration_minutes': 20,
            'location_type': 'online',
            'color': 5,
            'active': True,
        }
    ]
    
    for type_data in default_types:
        if not ServiceType.search([('code', '=', type_data['code'])]):
            ServiceType.create(type_data)