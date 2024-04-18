# Custom filters for use in templates
from django import template


register = template.Library()

@register.filter
def number_to_words(value):
    units = ['two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']

    if value < 0 or value > 9:
        return ""

    return units[value - 2]

