import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import os
from app.models.history import SentEmail
from app import db

class MailService:
    @staticmethod
    def test_connection(server_url, port, email, password, use_tls):
        """
        Attempts to connect and login to the SMTP server to verify credentials.
        """
        try:
            server = smtplib.SMTP(server_url, port, timeout=10)
            if use_tls:
                server.starttls()
            server.login(email, password)
            server.quit()
            return True, "Connexion réussie ! Vos paramètres sont corrects."
        except Exception as e:
            return False, str(e)

    @staticmethod
    def send_email(user, smtp_config, subject, body_html, recipients, attachments=None):
        """
        Sends an email using the user's SMTP configuration.
        recipients: list of email addresses
        attachments: list of file paths
        """
        if not smtp_config:
            return False, "Configuration SMTP manquante."

        try:
            # Setup SMTP server
            server = smtplib.SMTP(smtp_config.server, smtp_config.port)
            if smtp_config.use_tls:
                server.starttls()
            
            # Login
            server.login(smtp_config.email, smtp_config.get_smtp_password())
            
            results = []
            for recipient in recipients:
                try:
                    # Create message
                    msg = MIMEMultipart()
                    msg['From'] = smtp_config.email
                    msg['To'] = recipient
                    msg['Subject'] = subject
                    
                    # Add body
                    msg.attach(MIMEText(body_html, 'html'))
                    
                    # Add attachments
                    if attachments:
                        for file_path in attachments:
                            if os.path.exists(file_path):
                                filename = os.path.basename(file_path)
                                with open(file_path, "rb") as attachment:
                                    part = MIMEBase("application", "octet-stream")
                                    part.set_payload(attachment.read())
                                    encoders.encode_base64(part)
                                    part.add_header(
                                        "Content-Disposition",
                                        f"attachment; filename= {filename}",
                                    )
                                    msg.attach(part)
                    
                    # Send
                    server.send_message(msg)
                    
                    # Log success
                    sent_email = SentEmail(
                        user_id=user.id,
                        subject=subject,
                        recipient=recipient,
                        status='success'
                    )
                    db.session.add(sent_email)
                    results.append((recipient, True, None))
                    
                except Exception as e:
                    # Log failure for individual recipient
                    sent_email = SentEmail(
                        user_id=user.id,
                        subject=subject,
                        recipient=recipient,
                        status='failed',
                        error_message=str(e)
                    )
                    db.session.add(sent_email)
                    results.append((recipient, False, str(e)))
            
            db.session.commit()
            server.quit()
            return True, results
            
        except Exception as e:
            return False, str(e)
