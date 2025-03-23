#!/usr/bin/env python3
"""
Email Fetcher Module
------------------
Retrieves invoice emails and extracts PDF attachments.
"""

import os
import imaplib
import email
import getpass
import datetime
import tempfile
from pathlib import Path
from email.header import decode_header

class EmailFetcher:
    def __init__(self, config_file="email_config.json"):
        """
        Initialize email fetcher with configuration.
        
        Args:
            config_file: Path to JSON file with email credentials
        """
        self.config_file = config_file
        self.config = self._load_config()
        self.temp_dir = None
        
    def _load_config(self):
        """
        Load email configuration from file or prompt user.
        
        Returns:
            Dictionary with email configuration
        """
        # Default config
        config = {
            'imap_server': 'imap.mail.yahoo.com',
            'imap_port': 993,
            'username': '',
            'password': '',
            'folder': 'INBOX',
            'days_back': 3,
            'search_terms': ['invoice', 'statement', 'bill']
        }
        
        # Try to load from file
        if os.path.exists(self.config_file):
            try:
                import json
                with open(self.config_file, 'r') as f:
                    saved_config = json.load(f)
                    config.update(saved_config)
            except Exception as e:
                print(f"Error loading email config: {str(e)}")
                
        # If no username/password, prompt user
        if not config['username'] or not config['password']:
            print("\nEmail Configuration")
            print("-" * 30)
            
            config['username'] = input(f"Yahoo Email Address [{config['username']}]: ") or config['username']
            
            if not config['password']:
                config['password'] = getpass.getpass("Password: ")
                
            # Ask if we should save
            if input("Save credentials for future use? (y/n): ").lower() == 'y':
                self._save_config(config)
                
        return config
        
    def _save_config(self, config):
        """
        Save email configuration to file.
        
        Args:
            config: Dictionary with config values
        """
        try:
            import json
            # Create a copy without password for security
            save_config = config.copy()
            # Only save password if user explicitly agreed
            
            with open(self.config_file, 'w') as f:
                json.dump(save_config, f, indent=4)
                
            print(f"Config saved to {self.config_file}")
            
            # Set permissions to restrict access (Unix-like systems)
            try:
                os.chmod(self.config_file, 0o600)
            except:
                pass
                
        except Exception as e:
            print(f"Error saving email config: {str(e)}")
            
    def fetch_invoice_attachments(self):
        """
        Connect to email and download PDF invoice attachments.
        
        Returns:
            Path to folder containing downloaded attachments
        """
        # Create temp directory for attachments
        self.temp_dir = tempfile.mkdtemp(prefix="invoice_pdfs_")
        
        # Connect to IMAP server
        try:
            mail = imaplib.IMAP4_SSL(self.config['imap_server'], self.config['imap_port'])
            mail.login(self.config['username'], self.config['password'])
            mail.select(self.config['folder'])
            
            # Calculate date for search
            date_since = (datetime.datetime.now() - 
                          datetime.timedelta(days=self.config['days_back'])).strftime("%d-%b-%Y")
            
            # Search for relevant emails
            search_criteria = f'(SINCE {date_since})'
            status, messages = mail.search(None, search_criteria)
            
            if status != 'OK':
                print("No messages found.")
                return self.temp_dir
                
            message_ids = messages[0].split()
            print(f"Found {len(message_ids)} messages since {date_since}")
            
            # Process each message
            attachments_count = 0
            for msg_id in message_ids:
                status, msg_data = mail.fetch(msg_id, '(RFC822)')
                
                if status != 'OK':
                    continue
                    
                email_message = email.message_from_bytes(msg_data[0][1])
                
                # Check if the email might contain an invoice
                subject = self._decode_email_subject(email_message['Subject'])
                if not any(term.lower() in subject.lower() for term in self.config['search_terms']):
                    continue
                    
                print(f"Processing email: {subject}")
                
                # Extract PDF attachments
                if self._process_attachments(email_message, self.temp_dir):
                    attachments_count += 1
                    
            mail.close()
            mail.logout()
            
            print(f"Downloaded {attachments_count} invoice attachments to {self.temp_dir}")
            return self.temp_dir
            
        except Exception as e:
            print(f"Error fetching emails: {str(e)}")
            return self.temp_dir
            
    def _decode_email_subject(self, subject):
        """
        Decode email subject to readable text.
        
        Args:
            subject: Raw email subject
            
        Returns:
            Decoded subject string
        """
        if not subject:
            return ""
            
        try:
            decoded_header = decode_header(subject)
            subject_parts = []
            
            for content, encoding in decoded_header:
                if isinstance(content, bytes):
                    if encoding:
                        content = content.decode(encoding)
                    else:
                        content = content.decode('utf-8', errors='replace')
                subject_parts.append(content)
                
            return " ".join(subject_parts)
        except:
            # Fall back to basic string conversion
            return str(subject)
            
    def _process_attachments(self, email_message, download_dir):
        """
        Process and save attachments from an email message.
        
        Args:
            email_message: Email message object
            download_dir: Directory to save attachments
            
        Returns:
            True if any PDF attachments were found and saved
        """
        saved_any = False
        
        for part in email_message.walk():
            if part.get_content_maintype() == 'multipart':
                continue
                
            if part.get('Content-Disposition') is None:
                continue
                
            filename = part.get_filename()
            
            if not filename:
                continue
                
            # Decode filename if needed
            try:
                filename_parts = decode_header(filename)
                if filename_parts[0][1] is not None:
                    filename = filename_parts[0][0].decode(filename_parts[0][1])
                elif isinstance(filename_parts[0][0], bytes):
                    filename = filename_parts[0][0].decode('utf-8', errors='replace')
                else:
                    filename = str(filename_parts[0][0])
            except:
                # If decoding fails, use raw filename
                pass
                
            # Only process PDF files
            if not filename.lower().endswith('.pdf'):
                continue
                
            # Create safe filename (remove problematic characters)
            safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ").strip()
            
            # Add timestamp to prevent overwriting
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            if '.' in safe_filename:
                name, ext = safe_filename.rsplit('.', 1)
                safe_filename = f"{name}_{timestamp}.{ext}"
            else:
                safe_filename = f"{safe_filename}_{timestamp}"
                
            # Save the attachment
            filepath = os.path.join(download_dir, safe_filename)
            with open(filepath, 'wb') as f:
                f.write(part.get_payload(decode=True))
                
            print(f"Saved attachment: {safe_filename}")
            saved_any = True
            
        return saved_any
        
    def cleanup(self):
        """Clean up temporary files."""
        # This method could be expanded to remove temporary files
        # when they're no longer needed
        pass