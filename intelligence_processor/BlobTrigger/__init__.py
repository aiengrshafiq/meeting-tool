# intelligence_processor/BlobTrigger/__init__.py

import logging
import azure.functions as func
import os
import json
from datetime import datetime, timezone
from azure.storage.blob import BlobServiceClient

# Import our brain modules
from brain import classifier, queue_manager, vectorizer
from frontend.db import SessionLocal

from models import MeetingLog, ScheduledMeeting, User

def main(blob: func.InputStream):
    logging.info("--- INTELLIGENCE BRAIN TRIGGERED ---")
    
    db_session = None
    try:
        # --- 1. SETUP ---
        blob_name_parts = blob.name.split('/')
        meeting_id = blob_name_parts[1] # The real Meeting ID is the folder name

        logging.info(f"Processing blob: {blob.name} for Meeting ID: {meeting_id}")
        
        transcript_content = blob.read().decode('utf-8')
        logging.info("Successfully read blob content.")
        
        # --- 2. CLASSIFY ---
        db_session = SessionLocal()
        # --- FETCH REAL PARTICIPANTS ---
        participants_list = []
        user_list = [] # To store User objects for the training queue
        
        scheduled_meeting = db_session.query(ScheduledMeeting).filter(ScheduledMeeting.meeting_id == meeting_id).first()
        if scheduled_meeting and scheduled_meeting.participants:
            participant_emails = json.loads(scheduled_meeting.participants)
            logging.info(f"Found invited participants: {participant_emails}")
            
            for email in participant_emails:
                # Check if the participant is a registered internal user
                user = db_session.query(User).filter(User.email == email).first()
                if user:
                    # Internal user
                    participants_list.append(f"{user.email} (Internal)")
                    user_list.append(user)
                else:
                    # External guest
                    participants_list.append(f"{email} (External)")
        else:
            logging.warning(f"No scheduled meeting or participants found for {meeting_id}. Using placeholder.")
            participants_list = ["Syed Owais", "Rain"] # Fallback

        classification_result = classifier.classify_transcript(
            transcript_text=transcript_content, 
            participants=participants_list
        )

        if "error" in classification_result:
            raise Exception(f"Classification failed: {classification_result['error']}")
        logging.info(f"✅ Classification Result: {classification_result}")

        # --- 3. VECTORIZE ---
        current_utc_time = datetime.now(timezone.utc).isoformat()
        vectorizer.vectorize_and_save(
            transcript_text=transcript_content,
            classification_result=classification_result,
            meeting_id=meeting_id,
            meeting_date=current_utc_time
        )
        
        # --- 4. PREPARE FINAL OUTPUT AND PATH ---
        year = datetime.now(timezone.utc).strftime("%Y")
        subsidiary = classification_result.get("subsidiary", "UnknownSubsidiary").replace(" ", "")
        meeting_type = classification_result.get("meeting_type", "UnknownType").replace(" ", "")
        file_friendly_id = f"{current_utc_time.split('T')[0]}_{meeting_id}.json"
        output_blob_path = f"{year}/{subsidiary}/{meeting_type}/{file_friendly_id}"
        
        # --- 5. UPDATE DATABASE ---
        # db_session = SessionLocal()
        
        # Find the existing log created by the webhook
        meeting_log_to_update = db_session.query(MeetingLog).filter(MeetingLog.meeting_id == meeting_id).first()
        
        if meeting_log_to_update:
            logging.info(f"Found existing MeetingLog for {meeting_id}. Updating with AI metadata.")
            # Update the record with the new AI fields
            meeting_log_to_update.subsidiary = classification_result.get("subsidiary")
            meeting_log_to_update.department = classification_result.get("department")
            meeting_log_to_update.meeting_type = classification_result.get("meeting_type")
            meeting_log_to_update.meeting_subtype = classification_result.get("meeting_subtype")
            meeting_log_to_update.tags = classification_result.get("tags")
            meeting_log_to_update.key_decisions = classification_result.get("key_decisions")
            meeting_log_to_update.enriched_output_path = output_blob_path
        else:
            # This is a fallback in case the webhook failed to create the record
            logging.warning(f"No existing MeetingLog found for {meeting_id}. Creating a new one.")
            meeting_log_to_update = MeetingLog(
                meeting_id=meeting_id,
                summary="Summary to be generated.",
                transcript=transcript_content,
                recipients=json.dumps(participants_list),
                meeting_time=datetime.fromisoformat(current_utc_time),
                subsidiary=classification_result.get("subsidiary"),
                department=classification_result.get("department"),
                meeting_type=classification_result.get("meeting_type"),
                meeting_subtype=classification_result.get("meeting_subtype"),
                tags=classification_result.get("tags"),
                key_decisions=classification_result.get("key_decisions"),
                enriched_output_path=output_blob_path
            )
            db_session.add(meeting_log_to_update)

        #queue_manager.add_to_training_queue(db_session, classification_result, meeting_id, participants_list)
        queue_manager.add_to_training_queue(db_session, classification_result, meeting_id, user_list)
        
        db_session.commit()
        logging.info("✅ Database records committed successfully.")

        # --- 6. UPLOAD FINAL JSON OUTPUT ---
        final_json_output = {
          "meetingId": meeting_id,
          "dateTime": current_utc_time,
          "classification": classification_result,
          "participants": participants_list,
          "transcript_blob_path": blob.name
        }
        logging.info(f"Saving final JSON output to: {output_blob_path}")
        p2_storage_conn_str = os.getenv("AzureWebJobsStorage")
        blob_service_client = BlobServiceClient.from_connection_string(p2_storage_conn_str)
        blob_client = blob_service_client.get_blob_client(container="enriched-output-phase2", blob=output_blob_path)
        
        blob_client.upload_blob(json.dumps(final_json_output, indent=2), overwrite=True)
        logging.info("✅ Successfully uploaded final JSON output.")

    except Exception as e:
        if db_session:
            db_session.rollback()
        logging.error(f"Error processing blob '{blob.name}': {e}", exc_info=True)
    finally:
        if db_session:
            db_session.close()

    logging.info("--- TRIGGER PROCESSED SUCCESSFULLY ---")