from django import template
from datetime import datetime

register = template.Library()


@register.filter
def convert_data(string_data):
    return datetime.fromisoformat(string_data).date().strftime("%-d %b %Y")


@register.filter
def convert_time(string_data):
    return datetime.fromisoformat(string_data).time().strftime("%H:%M")
