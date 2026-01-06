from firebase_admin import messaging
from config.db_config import fcm_device_tokens_collection


async def send_push_notification(user_id: str, title: str, body: str, data: dict):

    devices = await fcm_device_tokens_collection.find(
        {
            "user_id": user_id,
            "status": "active"
        }
    ).to_list(length=10)

    if not devices:
        return

    for d in devices:
        try:
            message = messaging.Message(
                notification=messaging.Notification(
                    title=title,
                    body=body
                ),
                token=d["device_token"],
                data={k: str(v) for k, v in data.items()}
            )

            response = messaging.send(message)

        except Exception as e:
            print(f"[Push Failed for token {d['device_token']}] {e}")
