import re
import requests
from flask import current_app

MISTRAL_API_URL = "https://api.mistral.ai/v1/chat/completions"

SYSTEM_PROMPT = (
    "Tu es un rédacteur spécialisé dans la création de newsletters HTML. Ultra responsive (Couleurs verte jaune noir blanc) "
    "À partir de la demande de l'utilisateur, génère le contenu HTML complet du corps d'un email "
    "(pas de balises <html>, <head> ou <body>, uniquement le contenu à insérer dans le corps du message). "
    "Utilise des styles CSS en ligne (inline) pour une compatibilité maximale avec les clients mail, "
    "une mise en page simple et aérée, et du texte en français sauf indication contraire. "
    "Réponds uniquement avec le code HTML, sans explication, sans balises de code markdown (```)."
    "Toujours mettre le logo de l'entreprise (sur fond jaune car le logo est jaune) par email : https://www.joelcomputech.com/logo.png  (```)."
    "Pas d'images ou de bannières a part le logo."
)


class MistralService:
    @staticmethod
    def generate_html(prompt, previous_content=None):
        """
        Calls the Mistral API to generate email-safe HTML content from a text prompt.
        Returns (success, html_or_error_message).
        """
        api_key = current_app.config.get('MISTRAL_API_KEY')
        if not api_key:
            return False, "Clé API Mistral non configurée (MISTRAL_API_KEY)."

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        if previous_content:
            messages.append({
                "role": "assistant",
                "content": previous_content
            })
        messages.append({"role": "user", "content": prompt})

        try:
            response = requests.post(
                MISTRAL_API_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": current_app.config.get('MISTRAL_MODEL', 'mistral-large-latest'),
                    "messages": messages,
                    "temperature": 0.7
                },
                timeout=60
            )
            response.raise_for_status()
            data = response.json()
            html = data['choices'][0]['message']['content'].strip()
            html = MistralService._strip_code_fences(html)
            return True, html
        except requests.exceptions.RequestException as e:
            return False, f"Erreur lors de l'appel à Mistral : {e}"
        except (KeyError, IndexError):
            return False, "Réponse inattendue de l'API Mistral."

    @staticmethod
    def _strip_code_fences(text):
        match = re.match(r"^```(?:html)?\s*(.*?)\s*```$", text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return text
