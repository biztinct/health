# Health Zalo Integration Module

Integrates Zalo Official Account messaging into the Healthcare system for real-time patient communication.

## Features

### Core Functionality
- **Real-time Chat Interface**: Chat with Zalo users directly from Odoo
- **OAuth 2.0 Authentication**: Secure connection to Zalo Official Account
- **Webhook Integration**: Receive real-time message notifications from Zalo
- **Automatic Token Refresh**: Keeps your Zalo connection active
- **Message History**: Complete conversation and message storage
- **Attachment Support**: Send and receive images, files, and media

### Patient Integration
- **Contact Linking**: Connect Zalo users to Odoo contacts and patients
- **Zalo Actions**: Quick chat and call buttons on contact forms
- **Conversation Tracking**: View Zalo conversation history for each patient
- **Smart Notifications**: Real-time alerts for new messages via Odoo bus

### User Management
- **Role-Based Access**: Three security levels (User, Manager, Administrator)
- **Multi-Company Support**: Separate Zalo configurations per company
- **Follower Tracking**: Monitor which users follow your Official Account

## Installation

### Prerequisites
1. Python packages:
   ```bash
   pip install requests
   ```

2. Zalo Official Account:
   - Register at https://developers.zalo.me
   - Create a new Official Account application
   - Note your App ID, App Secret, and OA ID

### Installation Steps
1. Copy this module to your Odoo addons directory
2. Update the apps list: `Settings > Apps > Update Apps List`
3. Search for "Health Zalo Integration"
4. Click "Install"

## Configuration

### 1. Configure Zalo Official Account

1. Navigate to: **Zalo > Configuration > Zalo Settings**
2. Click "Create" to add a new configuration
3. Fill in the required fields:
   - **App ID**: Your Zalo App ID from developers.zalo.me
   - **App Secret**: Your Zalo App Secret (keep this secure!)
   - **OA ID**: Your Official Account ID

4. Click "Save"

### 2. Connect to Zalo

1. Click the **"Connect to Zalo"** button
2. You will be redirected to Zalo's authorization page
3. Log in with your Zalo account and authorize the app
4. You will be redirected back to Odoo with a connected status

### 3. Enable Webhooks

1. Click the **"Enable Webhook"** button
2. Copy the **Webhook URL** displayed
3. Register this URL in your Zalo app settings at developers.zalo.me:
   - Go to your app settings
   - Add the webhook URL
   - Subscribe to events: `user_send_text`, `user_send_image`, `user_send_file`, `follow`, `unfollow`

## Usage

### Sending Messages

#### From Conversations View
1. Navigate to: **Zalo > Conversations**
2. Select a conversation or wait for a user to message you
3. Click **"Open Chat"** to open the chat widget
4. Type your message and send

#### From Contact/Patient Record
1. Open any contact or patient record
2. If they have a Zalo User ID configured, you'll see Zalo action buttons
3. Click the chat icon to open Zalo chat
4. Click the phone icon to call via Zalo

### Receiving Messages

When a Zalo user sends a message:
1. A real-time notification appears in Odoo (via bus.bus)
2. The conversation is automatically created/updated
3. Unread message count is updated
4. You can respond directly from the notification or conversation view

### Linking Zalo Users to Contacts

1. Open a Zalo conversation
2. Click **"Link to Contact"**
3. Select the corresponding contact/patient record
4. The conversation will now appear on that contact's record

## Architecture

### Models
- **zalo.config**: OAuth configuration and API credentials
- **zalo.conversation**: Conversation threads with Zalo users
- **zalo.message**: Individual messages (text, images, files)
- **zalo.attachment**: Media attachments for messages
- **res.partner** (extended): Added Zalo integration fields
- **health.patient** (extended): Zalo integration for patients

### Services
- **zalo.api.client**: Zalo API wrapper (in services/zalo_api.py)
- **zalo.token.manager**: OAuth token management
- **zalo.message.handler**: Webhook event processing

### Controllers
- **`/zalo/webhook`**: Receives Zalo message notifications (POST)
- **`/zalo/oauth/callback`**: OAuth callback endpoint
- **`/zalo/chat/*`**: Chat interface API endpoints

### Security
- **Zalo User**: Can view and send messages
- **Zalo Manager**: Can configure conversations
- **Zalo Administrator**: Full configuration access (includes app secrets)

## API Reference

### Zalo Official Account API
This module uses Zalo OA API v2.0. Key endpoints:
- **Authentication**: `POST /v4/access_token`
- **Send Message**: `POST /v2.0/oa/message`
- **Get User Profile**: `GET /v2.0/oa/getprofile`
- **Get Followers**: `GET /v2.0/oa/getfollowers`

Full API documentation: https://developers.zalo.me/docs/official-account

### Python API Examples

```python
# Get active Zalo configuration
config = env['zalo.config'].get_active_config()

# Send a message
conversation = env['zalo.conversation'].find_or_create_conversation('zalo_user_id')
message = env['zalo.message'].create_outgoing_message(
    conversation,
    "Hello from Odoo!",
    'text'
)

# Process webhook event (called automatically by webhook controller)
env['zalo.message.handler'].process_webhook_event(event_data)
```

## Troubleshooting

### Connection Issues
- **Error: "No access token available"**
  - Solution: Reconnect to Zalo via "Connect to Zalo" button

- **Error: "Token expired"**
  - Solution: Click "Refresh Token" or wait for automatic refresh (runs hourly)

### Webhook Issues
- **Messages not arriving**
  - Check webhook is enabled in Odoo
  - Verify webhook URL is registered in Zalo app settings
  - Check webhook URL is publicly accessible (HTTPS required)
  - Review Odoo logs for webhook errors

### Message Sending Failures
- **Error: "Failed to send message"**
  - Verify token is not expired
  - Check user is following your Official Account
  - Ensure message content complies with Zalo policies

## Technical Notes

### OAuth Token Lifecycle
- Access tokens expire after ~1 hour
- Automatic refresh runs every hour (cron job)
- Manual refresh available via "Refresh Token" button
- Tokens stored securely (visible only to system administrators)

### Webhook Requirements
- Must respond within 2 seconds (enforced by Zalo)
- Uses async processing queue for heavy operations
- Signature validation via HMAC SHA-256

### Real-time Notifications
- Uses Odoo's built-in bus.bus for real-time updates
- No custom WebSocket server required
- Notifications scoped by company

## Future Enhancements (Phase 2+)

Planned features for future releases:
- [ ] Owl.js chat widget UI component
- [ ] ZNS template notification support
- [ ] Rich message templates (buttons, quick replies)
- [ ] Chat analytics and reporting
- [ ] Automated chatbot responses
- [ ] Group messaging support
- [ ] Message scheduling
- [ ] Broadcast campaigns

## Support

For issues, feature requests, or questions:
- Check module documentation in `/doc` folder
- Review Zalo API documentation: https://developers.zalo.me
- Contact: I Am Dream Catcher Ltd

## License

LGPL-3

## Credits

**Author**: I Am Dream Catcher Ltd
**Maintainer**: I Am Dream Catcher Ltd
**Version**: 18.0.1.0.0
