from services.translation import translate_message


def signup_verification_template(username: str, otp: str, lang: str):
    
    subject = translate_message("EMAIL_SIGNUP_SUBJECT", lang=lang)

    greeting = translate_message("EMAIL_SIGNUP_GREETING", lang=lang).format(username=username)
    line1 = translate_message("EMAIL_SIGNUP_LINE1", lang=lang)
    line2 = translate_message("EMAIL_SIGNUP_LINE2", lang=lang)
    validity = translate_message("EMAIL_SIGNUP_VALIDITY", lang=lang)
    ignore_text = translate_message("EMAIL_SIGNUP_IGNORE", lang=lang)
    footer = translate_message("EMAIL_SIGNUP_FOOTER", lang=lang)
    team = translate_message("EMAIL_TEAM", lang=lang)

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 12px;">
            
            <h2 style="color: #333;">{greeting}</h2>

            <p style="font-size: 15px; color: #555;">
                {line1}
            </p>

            <p style="font-size: 15px; color: #555;">
                {line2}
            </p>

            <div style="text-align: center; margin: 25px 0;">
                <h1 style="letter-spacing: 6px; font-size: 32px; color: #E91E63;">
                    {otp}
                </h1>
            </div>

            <p style="font-size: 14px; color: #777;">
                {validity}
            </p>

            <p style="font-size: 14px; color: #777;">
                {ignore_text}
            </p>

            <p style="margin-top: 25px; font-size: 14px; color: #999;">
                {footer}<br/>
                {team}
            </p>

        </div>
    </body>
    </html>
    """
    return subject, body

def login_verification_template(username: str, otp: str, lang: str):

    subject = translate_message("EMAIL_LOGIN_SUBJECT", lang=lang)

    greeting = translate_message("EMAIL_LOGIN_GREETING", lang=lang).format(username=username)
    line1 = translate_message("EMAIL_LOGIN_LINE1", lang=lang)
    validity = translate_message("EMAIL_LOGIN_VALIDITY", lang=lang)
    security = translate_message("EMAIL_LOGIN_SECURITY", lang=lang)
    footer = translate_message("EMAIL_LOGIN_FOOTER", lang=lang)
    team = translate_message("EMAIL_TEAM", lang=lang)

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f9f9f9;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 12px;">

            <h2>{greeting}</h2>

            <p>{line1}</p>

            <div style="text-align:center; margin: 20px 0;">
                <h1 style="letter-spacing: 6px; color: #E91E63;">
                    {otp}
                </h1>
            </div>

            <p>{validity}</p>

            <p>{security}</p>

            <p style="margin-top: 25px;">
                {footer}<br/>
                {team}
            </p>

        </div>
    </body>
    </html>
    """
    return subject, body

def reset_password_otp_template(username: str, otp: str, lang: str):

    subject = translate_message("EMAIL_RESET_SUBJECT", lang=lang)

    greeting = translate_message("EMAIL_RESET_GREETING", lang=lang).format(username=username)
    line1 = translate_message("EMAIL_RESET_LINE1", lang=lang)
    line2 = translate_message("EMAIL_RESET_LINE2", lang=lang)
    validity = translate_message("EMAIL_RESET_VALIDITY", lang=lang)
    ignore_text = translate_message("EMAIL_RESET_IGNORE", lang=lang)
    footer = translate_message("EMAIL_RESET_FOOTER", lang=lang)
    team = translate_message("EMAIL_TEAM", lang=lang)

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; padding: 20px; background-color: #f9f9f9;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 12px;">

            <h2>{greeting}</h2>

            <p>{line1}</p>

            <p>{line2}</p>

            <div style="text-align:center; margin: 20px 0;">
                <h1 style="letter-spacing: 6px; color: #E91E63;">
                    {otp}
                </h1>
            </div>

            <p>{validity}</p>

            <p>{ignore_text}</p>

            <p style="margin-top: 25px;">
                {footer}<br/>
                {team}
            </p>

        </div>
    </body>
    </html>
    """
    return subject, body

def onboarding_completed_template(username: str, lang: str):

    subject = translate_message("EMAIL_ONBOARDING_SUBJECT", lang=lang)

    greeting = translate_message("EMAIL_ONBOARDING_GREETING", lang=lang).format(username=username)
    line1 = translate_message("EMAIL_ONBOARDING_LINE1", lang=lang)
    line2 = translate_message("EMAIL_ONBOARDING_LINE2", lang=lang)
    line3 = translate_message("EMAIL_ONBOARDING_LINE3", lang=lang)
    footer = translate_message("EMAIL_ONBOARDING_FOOTER", lang=lang)
    team = translate_message("EMAIL_TEAM", lang=lang)

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 12px;">

            <h2>{greeting}</h2>

            <p>{line1}</p>

            <p>{line2}</p>

            <p>{line3}</p>

            <p style="margin-top: 25px;">
                {footer}<br/>
                {team}
            </p>

        </div>
    </body>
    </html>
    """

    return subject, body

def verification_approved_template(username: str, lang: str):

    subject = translate_message("EMAIL_APPROVED_SUBJECT", lang=lang)

    greeting = translate_message("EMAIL_APPROVED_GREETING", lang=lang).format(username=username)
    line1 = translate_message("EMAIL_APPROVED_LINE1", lang=lang)
    line2 = translate_message("EMAIL_APPROVED_LINE2", lang=lang)
    line3 = translate_message("EMAIL_APPROVED_LINE3", lang=lang)
    team = translate_message("EMAIL_TEAM", lang=lang)

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 12px;">

            <h2>{greeting}</h2>

            <p>{line1}</p>

            <p>{line2}</p>

            <p>{line3}</p>

            <p style="margin-top: 25px;">
                {team}
            </p>

        </div>
    </body>
    </html>
    """

    return subject, body

def verification_rejected_template(username: str, lang: str):

    subject = translate_message("EMAIL_REJECTED_SUBJECT", lang=lang)

    greeting = translate_message("EMAIL_REJECTED_GREETING", lang=lang).format(username=username)
    line1 = translate_message("EMAIL_REJECTED_LINE1", lang=lang)
    line2 = translate_message("EMAIL_REJECTED_LINE2", lang=lang)
    line3 = translate_message("EMAIL_REJECTED_LINE3", lang=lang)
    team = translate_message("EMAIL_TEAM", lang=lang)

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f9f9f9; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 30px; border-radius: 12px;">

            <h2>{greeting}</h2>

            <p>{line1}</p>

            <p>{line2}</p>

            <p>{line3}</p>

            <p style="margin-top: 25px;">
                {team}
            </p>

        </div>
    </body>
    </html>
    """

    return subject, body

def subscription_expiry_template(username: str, lang:str = "en"):
    subscription_expiry_template_translation = {
        "en": {
            "title": "Your MILA Subscription Expires Soon",
            "body": f"""Hi {username},
            
Just a quick reminder — your MILA Premium subscription is set to expire in 3 days.

We hope you’ve been enjoying the extra perks, including enhanced visibility, exclusive features, and better connections. 💖

To continue enjoying uninterrupted access to all premium benefits, please renew your subscription before it expires.

Renew now and keep the conversations, matches, and moments going. ✨

If you have any questions or need assistance, we’re always here to help.
            
— Team MILA
            """
        },
        "fr": {
            "title": "Votre abonnement MILA expire bientôt",
            "body": f"""Salut {username},
            
Petit rappel : votre abonnement MILA Premium expire dans 3 jours.

Nous espérons que vous avez profité des avantages supplémentaires, comme une meilleure visibilité, des fonctionnalités exclusives et des rencontres plus enrichissantes. 💖
    
Pour continuer à bénéficier d'un accès illimité à tous les avantages Premium, veuillez renouveler votre abonnement avant son expiration.
    
Renouvelez dès maintenant et poursuivez vos conversations, vos rencontres et vos moments inoubliables. ✨
    
Si vous avez des questions ou besoin d'aide, nous sommes toujours là pour vous.

— L'équipe MILA
        """
        }
    }

    return subscription_expiry_template_translation[lang]
