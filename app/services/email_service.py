import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from app.core.config import get_settings

logger = logging.getLogger("plantguard.email")
settings = get_settings()

def send_otp_email(email: str, otp_code: str) -> bool:
    """
    Sends a 6-digit OTP code to the farmer's email using Gmail SMTP.
    Returns True if sent successfully, False otherwise.
    The email is bilingual (English + Nepali) and mobile-friendly.
    """
    # 1. Build the HTML email body
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>PlantGuard Password Reset</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f4; padding: 20px 0;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                        <!-- Green Header -->
                        <tr>
                            <td style="background-color: #10b981; padding: 30px; text-align: center;">
                                <h1 style="color: #ffffff; margin: 0; font-size: 28px; font-weight: bold;">🌱 PlantGuard</h1>
                                <p style="color: #d1fae5; margin: 8px 0 0 0; font-size: 14px;">Secure Plant Disease Diagnosis</p>
                            </td>
                        </tr>
                        <!-- Email Body -->
                        <tr>
                            <td style="padding: 40px 30px;">
                                <!-- English Section -->
                                <h2 style="color: #1f2937; font-size: 20px; margin: 0 0 16px 0;">Password Reset Code</h2>
                                <p style="color: #4b5563; font-size: 16px; line-height: 1.6; margin: 0 0 24px 0;">
                                    You requested to reset your PlantGuard password. Use the code below to create a new password.
                                </p>
                                <!-- OTP Code Box -->
                                <table width="100%" cellpadding="0" cellspacing="0" style="margin: 0 0 24px 0;">
                                    <tr>
                                        <td align="center" style="background-color: #f0fdf4; border: 2px dashed #10b981; border-radius: 8px; padding: 24px;">
                                            <h1 style="color: #059669; font-size: 36px; letter-spacing: 8px; margin: 0; font-family: monospace; font-weight: bold;">
                                                {otp_code}
                                            </h1>
                                        </td>
                                    </tr>
                                </table>
                                <p style="color: #6b7280; font-size: 14px; margin: 0 0 32px 0;">
                                    ⏰ This code expires in <strong>{settings.OTP_EXPIRE_MINUTES} minutes</strong>.<br>
                                    If you did not request this, please ignore this email.
                                </p>
                                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 32px 0;">
                                <!-- Nepali Section -->
                                <h2 style="color: #1f2937; font-size: 18px; margin: 0 0 12px 0;">पासवर्ड रिसेट कोड</h2>
                                <p style="color: #4b5563; font-size: 15px; line-height: 1.6; margin: 0 0 16px 0;">
                                    तपाईंले PlantGuard पासवर्ड रिसेट गर्न अनुरोध गर्नुभयो। नयाँ पासवर्ड बनाउन तलको कोड प्रयोग गर्नुहोस्।
                                </p>
                                <p style="color: #6b7280; font-size: 14px; margin: 0;">
                                    ⏰ यो कोड <strong>{settings.OTP_EXPIRE_MINUTES} मिनेट</strong>मा समाप्त हुन्छ।<br>
                                    यदि तपाईंले यो अनुरोध गर्नुभएन भने, कृपया यो इमेल बेवास्ता गर्नुहोस्।
                                </p>
                            </td>
                        </tr>
                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #f9fafb; padding: 20px; text-align: center; border-top: 1px solid #e5e7eb;">
                                <p style="color: #9ca3af; font-size: 12px; margin: 0;">
                                    © 2026 PlantGuard Group 31 | Capstone Project<br>
                                    This is an automated message. Please do not reply.
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """

    # 2. Configure the email message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your PlantGuard Reset Code: {otp_code}"
    msg["From"] = settings.SMTP_EMAIL
    msg["To"] = email
    msg.attach(MIMEText(html_content, "html"))

    # 3. Send via Gmail SMTP
    try:
        # Create a secure SSL context
        context = ssl.create_default_context()
        
        # Connect to Gmail's SMTP server
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(settings.SMTP_EMAIL, settings.SMTP_APP_PASSWORD)
            server.send_message(msg)
            
        logger.info(f"✅ OTP email sent successfully to {email}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Failed to send OTP email to {email}: {str(e)}")
        return False