#!/usr/bin/env python3
"""
Invoice Processor - Main Application
-----------------------------------
This program extracts data from supplier invoices and organizes it into Excel sheets.
It supports both summary invoice data and detailed line-item extraction.
"""

import os
import sys
import argparse
import logging
from datetime import datetime

from invoice_parser import InvoiceParser
from excel_manager import ExcelManager
from email_fetcher import EmailFetcher
from vendor_config import VendorConfig
from item_database import ItemDatabase
from llm_analyzer import LLMAnalyzer

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('invoice_processor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def setup_argparse():
    """Configure command-line argument parsing."""
    parser = argparse.ArgumentParser(description='Process supplier invoices and export to Excel.')
    parser.add_argument('--email', action='store_true', help='Fetch invoices from email')
    parser.add_argument('--train', action='store_true', help='Enter training mode for vendor templates')
    parser.add_argument('--vendor', type=str, help='Specify vendor for training')
    parser.add_argument('--pdf', type=str, help='Process a specific PDF file')
    parser.add_argument('--folder', type=str, help='Process all PDFs in a folder')
    parser.add_argument('--output', type=str, default='invoice_data.xlsx', 
                        help='Output Excel file (default: invoice_data.xlsx)')
    parser.add_argument('--item-db', type=str, default='item_database.xlsx',
                        help='Output Excel file for item database (default: item_database.xlsx)')
    parser.add_argument('--mode', type=str, choices=['summary', 'items', 'full'], default='full',
                        help='Processing mode: summary only, items only, or full (both)')
    parser.add_argument('--analyze', action='store_true', help='Run LLM analysis after processing')
    parser.add_argument('--silent', action='store_true', help='Run in silent mode (for automated execution)')
    return parser.parse_args()

def process_single_pdf(parser, excel_manager, item_db, pdf_path, mode='full', interactive=True):
    """Process a single PDF invoice."""
    try:
        logger.info(f"Processing: {pdf_path}")
        
        # Extract summary invoice data
        if mode in ['summary', 'full']:
            invoice_data = parser.extract_from_pdf(pdf_path)
            
            if not invoice_data:
                logger.warning(f"No invoice data found in {pdf_path}")
                return False
                
            for invoice in invoice_data:
                if interactive:
                    if input(f"Invoice total: ${invoice['total_cost']}. Use same amount for job cost? (y/n): ").lower() != 'y':
                        try:
                            invoice['job_cost'] = float(input("Enter job cost: $"))
                        except ValueError:
                            logger.warning("Invalid amount. Using total cost as job cost.")
                            invoice['job_cost'] = invoice['total_cost']
                    else:
                        invoice['job_cost'] = invoice['total_cost']
                else:
                    # In non-interactive mode, default to using the total cost
                    invoice['job_cost'] = invoice['total_cost']
                    
                # Add to Excel sheet organized by date
                excel_manager.add_invoice(invoice)
        
        # Extract line items
        if mode in ['items', 'full']:
            vendor_name = parser.identify_vendor(pdf_path)
            if vendor_name:
                items = parser.extract_line_items(pdf_path, vendor_name)
                if items:
                    for item in items:
                        item_db.add_item(item)
                    logger.info(f"Added {len(items)} items to database from {pdf_path}")
                else:
                    logger.warning(f"No line items extracted from {pdf_path}")
            else:
                logger.warning(f"Could not identify vendor for {pdf_path} - skipping line item extraction")
            
        return True
    except Exception as e:
        logger.error(f"Error processing {pdf_path}: {str(e)}", exc_info=True)
        return False

def process_folder(parser, excel_manager, item_db, folder_path, mode='full', interactive=True):
    """Process all PDF files in a folder."""
    success_count = 0
    fail_count = 0
    
    if not os.path.isdir(folder_path):
        logger.error(f"Error: {folder_path} is not a valid directory")
        return
        
    for filename in os.listdir(folder_path):
        if filename.lower().endswith('.pdf'):
            pdf_path = os.path.join(folder_path, filename)
            if process_single_pdf(parser, excel_manager, item_db, pdf_path, mode, interactive):
                success_count += 1
            else:
                fail_count += 1
    
    logger.info(f"Processing complete. Success: {success_count}, Failed: {fail_count}")

def train_vendor(vendor_config, vendor_name):
    """Train the system to recognize invoice fields for a specific vendor."""
    if not vendor_name:
        vendor_name = input("Enter vendor name: ")
    
    pdf_path = input("Enter path to sample invoice PDF: ")
    if not os.path.isfile(pdf_path) or not pdf_path.lower().endswith('.pdf'):
        logger.error("Invalid PDF file path.")
        return
        
    print("\nTraining mode for vendor: " + vendor_name)
    print("You'll need to identify where to find key information in the invoice.")
    
    # Use vendor_config to guide the training process
    vendor_config.create_or_update_vendor(vendor_name, pdf_path)
    logger.info(f"Training complete for {vendor_name}")
    
    # Ask about line item training
    if input("\nDo you want to train line item extraction for this vendor? (y/n): ").lower() == 'y':
        vendor_config.train_line_item_extraction(vendor_name, pdf_path)
        logger.info(f"Line item training complete for {vendor_name}")

def main():
    """Main application entry point."""
    args = setup_argparse()
    
    # Configure for silent mode if requested
    if args.silent:
        logging.getLogger().setLevel(logging.ERROR)
        interactive = False
    else:
        interactive = True
    
    # Initialize core components
    vendor_config = VendorConfig()
    parser = InvoiceParser(vendor_config)
    excel_manager = ExcelManager(args.output)
    item_db = ItemDatabase(args.item_db)
    
    # Handle training mode
    if args.train:
        train_vendor(vendor_config, args.vendor)
        return
    
    # Process PDF(s)
    if args.pdf:
        if os.path.isfile(args.pdf):
            process_single_pdf(parser, excel_manager, item_db, args.pdf, args.mode, interactive)
        else:
            logger.error(f"Error: File not found - {args.pdf}")
            
    elif args.folder:
        process_folder(parser, excel_manager, item_db, args.folder, args.mode, interactive)
        
    # Fetch and process emails if requested
    elif args.email:
        email_fetcher = EmailFetcher()
        pdf_folder = email_fetcher.fetch_invoice_attachments()
        if pdf_folder:
            process_folder(parser, excel_manager, item_db, pdf_folder, args.mode, interactive)
    
    # No specific action, show help
    else:
        print("Please specify an action (--train, --pdf, --folder, or --email)")
        print("Use --help for more information")
        return
    
    # Save any changes to Excel and database
    excel_manager.save()
    item_db.save()
    logger.info(f"Invoice data saved to {args.output}")
    logger.info(f"Item data saved to {args.item_db}")
    
    # Run LLM analysis if requested
    if args.analyze:
        try:
            analyzer = LLMAnalyzer(item_db)
            results = analyzer.analyze_recent_data()
            print("\nLLM Analysis Results:")
            print(results)
            logger.info("LLM analysis completed successfully")
        except Exception as e:
            logger.error(f"Error during LLM analysis: {str(e)}", exc_info=True)
    
if __name__ == "__main__":
    main()