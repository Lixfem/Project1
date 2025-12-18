from django.core.exceptions import ValidationError
from django.contrib.auth.tokens import PasswordResetTokenGenerator

class ConntainsLetterValidator:
    def validate(self, password, user=None):
        if not any(char.isalpha() for char in password):
            raise ValidationError(
                'Le mot de passe doit contenir au moins une lettre.',
                code= 'password_no_letters')
    
    def get_help_text(self):
        return 'Votre mot de passe doit contenir au moins une lettre majuscule ou minuscule.'


class ThirtyMinutesTokenGenerator(PasswordResetTokenGenerator):
    def _make_hash_value(self, user, timestamp):
        # On utilise les 30 dernières minutes seulement
        login_timestamp = '' if user.last_login is None else user.last_login.replace(microsecond=0, second=0)
        return f"{user.pk}{user.password}{login_timestamp}{timestamp}"

short_token_generator = ThirtyMinutesTokenGenerator()