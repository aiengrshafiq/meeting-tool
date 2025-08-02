# intelligence_processor/brain/queue_manager.py
import logging
from sqlalchemy.orm import Session
from models import TrainingQueue, MeetingLog, User

# THE FIX: The function now accepts the meeting_log object directly
# and a list of internal User objects.
def add_to_training_queue(db: Session, classification_result: dict, meeting_log: MeetingLog, internal_users: list[User]):
    """
    Checks for coaching-related tags and adds entries to the training queue in PostgreSQL.
    """
    coaching_tags = {"#Coaching", "#Escalation", "#Leadership", "#Training", "#Blocker", "#Breakthrough"}
    
    found_tags = coaching_tags.intersection(classification_result.get("tags", []))
    
    if not found_tags:
        logging.info("No coaching tags found. Skipping training queue.")
        return

    logging.info(f"Coaching tags found: {', '.join(found_tags)}. Adding to training queue for meeting {meeting_log.meeting_id}.")
    
    # For each internal user who was invited, create a training queue entry
    for user in internal_users:
        for tag in found_tags:
            new_training_entry = TrainingQueue(
                # THE FIX: Use the integer ID from the meeting_log object
                meeting_id=meeting_log.id, 
                participant_user_id=user.id,
                coaching_category=tag.replace("#", "")
            )
            db.add(new_training_entry)
            logging.info(f"Staged training entry for user '{user.email}' with category '{tag}'")
    
    return True