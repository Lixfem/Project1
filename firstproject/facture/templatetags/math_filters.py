from django import template

register = template.Library()

@register.filter
def multiply(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''
    
@register.filter   
def divide(value, arg):
    try:
        return float(value) / float(arg)
    except  (ValueError, TypeError):
        return ''