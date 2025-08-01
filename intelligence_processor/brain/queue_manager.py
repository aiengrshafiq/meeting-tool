# intelligence_processor/brain/queue_manager.py
import logging
from sqlalchemy.orm import Session
from models import TrainingQueue, MeetingLog, User

def add_to_training_queue(db: Session, classification_result: dict, meeting_id: str, participants: list):
    """
    Checks for coaching-related tags and adds entries to the training queue in PostgreSQL.
    """
    coaching_tags = {"#Coaching", "#Escalation", "#Leadership", "#Training", "#Blocker", "#Breakthrough"}
    
    # Use set intersection to find which coaching tags are in our result
    found_tags = coaching_tags.intersection(classification_result.get("tags", []))
    
    if not found_tags:
        logging.info("No coaching tags found. Skipping training queue.")
        return

    logging.info(f"Coaching tags found: {', '.join(found_tags)}. Adding to training queue for meeting {meeting_id}.")
    
    # Get the meeting log entry to link to
    meeting_log = db.query(MeetingLog).filter(MeetingLog.meeting_id == meeting_id).first()
    if not meeting_log:
        logging.error(f"Could not find MeetingLog entry for meeting_id: {meeting_id}. Cannot add to training queue.")
        # NOTE: We need to make sure the meeting log is created first.
        # This will be handled by saving the final JSON to the DB as well.
        # For now, this check might fail. We will fix this in a later step.
        return

    # For each participant, create a training queue entry for each relevant tag
    for participant_name in participants:
        # TODO: This is a placeholder. In a real system, you would look up the user's ID.
        # For now, we'll assume a user with ID 1 exists for testing.
        user = db.query(User).filter(User.id == 1).first() # Dummy lookup
        
        if user:
            for tag in found_tags:
                new_training_entry = TrainingQueue(
                    meeting_id=meeting_log.id,
                    participant_user_id=user.id,
                    coaching_category=tag.replace("#", "") # Store without the hashtag
                )
                db.add(new_training_entry)
                logging.info(f"Staged training entry for '{participant_name}' with category '{tag}'")
    
    # The commit will happen in the main __init__.py file
    return True