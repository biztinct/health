# Project TODO List

## Completed Tasks

### ✅ Automatic GPS Geocoding on Address Change
- Implemented synchronous pre-geocoding before form save
- Coordinates calculated and included in single write operation
- Backend working correctly

### ✅ Map Auto-Refresh on Coordinate Change
- Discovered invisible form fields don't trigger OWL reactive updates
- Implemented polling mechanism (500ms interval) to detect coordinate changes
- Map now updates instantly when coordinates change
- Polling cleaned up on component unmount
- Console logs cleaned up for production use

### ✅ Form Field Changes Hidden from Chatter + Audit Log
- Created filtering mechanism in _message_log() override
- Separates visible and hidden tracking values
- Uses 'user_notification' message_type to hide from chatter
- Tracking records attached to messages and visible in Audit Log
- Hidden fields: first_name, last_name, birth_date, gender, patient_code, address fields, etc.
- Visible fields: notes, messages, other non-sensitive data still show in chatter
- Audit Log correctly displays all changes including hidden fields

---

## Known Limitations

- Websocket connection error on port 8072 (not related to health module, infrastructure issue)

