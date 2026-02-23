def signup_verification_template(username: str, otp: str):
    subject = "Verify Your Email for MILA"

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f6f6f6; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 25px; border-radius: 10px;">
            <h2 style="color: #333;">Welcome to <strong>MILA</strong>, {username}!</h2>
            <p style="font-size: 15px; color: #555;">
                Use the verification code below to complete your signup:
            </p>

            <div style="text-align: center; margin: 25px 0;">
                <h1 style="letter-spacing: 5px; font-size: 32px; color: #2c3e50;">
                    {otp}
                </h1>
            </div>

            <p style="font-size: 14px; color: #777;">
                This code is valid for 5 minutes. Do not share it with anyone.
            </p>

            <p style="margin-top: 25px; font-size: 14px; color: #aaa;">
                — MILA Team
            </p>
        </div>
    </body>
    </html>
    """
    return subject, body

def login_verification_template(username: str, otp: str):
    subject = "Your MILA Login Verification Code"

    body = f"""
    <html>
        <body style="font-family: Arial; padding: 20px;">
            <h2>Hello {username},</h2>

            <p>Your login verification code is:</p>

            <h1 style="letter-spacing: 4px; color: #E91E63;">{otp}</h1>

            <p>This code will expire in <strong>5 minutes</strong>.</p>

            <br/>
            <p style="font-size: 12px; color: #888;">Team MILA</p>
        </body>
    </html>
    """
    return subject, body

def reset_password_otp_template(username, otp):
    subject = "Reset Your Password - MILA"
    body = f"""
    <p>Hello <b>{username}</b>,</p>
    <p>Your MILA password reset code is:</p>
    <h2>{otp}</h2>
    <p>This code will expire in 5 minutes.</p>
    """
    return subject, body

def onboarding_completed_template(username: str):
    subject = "Onboarding Completed Successfully 🎉"

    body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; background-color: #f6f6f6; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: white; padding: 25px; border-radius: 10px;">
            <h2 style="color: #333;">
                Hi {username},
            </h2>

            <p style="font-size: 15px; color: #555;">
                Your onboarding has been completed successfully.
            </p>

            <p style="font-size: 15px; color: #555;">
                You can now explore all features and start connecting on <strong>MILA</strong>.
            </p>

            <p style="margin-top: 25px; font-size: 14px; color: #aaa;">
                — MILA Team
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
