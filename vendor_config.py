#!/usr/bin/env python3
"""
Vendor Configuration Module
--------------------------
Manages vendor-specific templates for invoice data extraction.
Includes support for line item extraction configuration.
"""

import os
import json
import re
import logging
from pathlib import Path
from tabulate import tabulate

logger = logging.getLogger(__name__)

class VendorConfig:
    def __init__(self, config_path="vendor_config.json"):
        """
        Initialize vendor configuration manager.
        
        Args:
            config_path: Path to the JSON config file for vendors
        """
        self.config_path = config_path
        self.vendors = self._load_config()
        
    def _load_config(self):
        """
        Load vendor configurations from JSON file.
        
        Returns:
            Dictionary of vendor configurations
        """
        if not os.path.exists(self.config_path):
            # Create a default config file if it doesn't exist
            default_config = {}
            self._save_config(default_config)
            return default_config
            
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading vendor config: {str(e)}")
            return {}
            
    def _save_config(self, config=None):
        """
        Save vendor configurations to JSON file.
        
        Args:
            config: Config dictionary to save (uses self.vendors if None)
        """
        if config is None:
            config = self.vendors
            
        try:
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            logger.error(f"Error saving vendor config: {str(e)}")
            
    def get_vendor_rules(self, vendor_name):
        """
        Get extraction rules for a specific vendor.
        
        Args:
            vendor_name: Name of the vendor
            
        Returns:
            Dictionary of vendor-specific rules
        """
        return self.vendors.get(vendor_name, {})
        
    def create_or_update_vendor(self, vendor_name, sample_pdf_path):
        """
        Create or update vendor configuration through an interactive training process.
        
        Args:
            vendor_name: Name of the vendor
            sample_pdf_path: Path to a sample PDF from this vendor
        """
        from invoice_parser import InvoiceParser
        
        # Create a temporary parser just for extracting text
        temp_parser = InvoiceParser(self)
        sample_text = temp_parser.extract_training_page(sample_pdf_path)
        
        if not sample_text:
            logger.error("Failed to extract text from the sample PDF.")
            return
            
        # Display the sample text for reference
        print("\n" + "="*80)
        print("SAMPLE INVOICE TEXT (FIRST PAGE)")
        print("="*80)
        print(sample_text)
        print("="*80 + "\n")
        
        # Create or update vendor config
        vendor_config = self.vendors.get(vendor_name, {})
        
        # Set basic vendor info
        vendor_config['name'] = vendor_name
        
        # Set vendor identifier
        if 'identifier' not in vendor_config:
            print("\nWhat text uniquely identifies this vendor's invoices?")
            print("(This is used to automatically recognize the vendor)")
            vendor_config['identifier'] = input("Identifier text: ").strip()
        
        # Ask about multiple invoices
        if 'multiple_invoices' not in vendor_config:
            multiple = input("\nCan this vendor include multiple invoices in one PDF? (y/n): ").lower() == 'y'
            vendor_config['multiple_invoices'] = multiple
            
            if multiple:
                print("\nWhat text pattern separates individual invoices?")
                print("(This should be a unique text that appears at the start of each invoice)")
                separator = input("Separator pattern: ").strip()
                vendor_config['invoice_separator'] = separator
        
        # Train date extraction
        print("\nLet's find the invoice date.")
        print("In the sample text above, copy a small section containing the date:")
        date_sample = input("Text sample with date: ").strip()
        
        if date_sample:
            # Try to build a regex pattern for the date
            date_pattern = self._build_pattern_from_sample(date_sample, r'\d{1,2}/\d{1,2}/\d{2,4}')
            if date_pattern:
                vendor_config['date_pattern'] = date_pattern
                print(f"Date pattern: {date_pattern}")
                
                date_format = input("\nEnter the date format (default is MM/DD/YYYY): ").strip()
                if date_format:
                    vendor_config['date_format'] = date_format
                else:
                    vendor_config['date_format'] = "%m/%d/%Y"
        
        # Train job name extraction
        print("\nLet's find the job name.")
        print("In the sample text above, copy a small section containing the job name:")
        job_sample = input("Text sample with job name: ").strip()
        
        if job_sample:
            job_text = input("Enter the exact job name from your sample: ").strip()
            if job_text:
                job_pattern = self._build_pattern_from_sample(job_sample, re.escape(job_text))
                if job_pattern:
                    vendor_config['job_name_pattern'] = job_pattern
                    print(f"Job name pattern: {job_pattern}")
        
        # Train total cost extraction
        print("\nLet's find the total cost/amount.")
        print("In the sample text above, copy a small section containing the total amount:")
        total_sample = input("Text sample with total cost: ").strip()
        
        if total_sample:
            total_text = input("Enter the exact total amount from your sample (e.g. 1234.56): ").strip()
            if total_text:
                # Remove non-numeric characters for matching
                total_clean = re.sub(r'[^\d.]', '', total_text)
                total_pattern = self._build_pattern_from_sample(total_sample, r'\$?\s*[\d,]+\.\d{2}')
                if total_pattern:
                    vendor_config['total_cost_pattern'] = total_pattern
                    print(f"Total cost pattern: {total_pattern}")
        
        # Train invoice number extraction
        print("\nLet's find the invoice number.")
        print("In the sample text above, copy a small section containing the invoice number:")
        invoice_sample = input("Text sample with invoice number: ").strip()
        
        if invoice_sample:
            invoice_text = input("Enter the exact invoice number from your sample: ").strip()
            if invoice_text:
                invoice_pattern = self._build_pattern_from_sample(invoice_sample, re.escape(invoice_text))
                if invoice_pattern:
                    vendor_config['invoice_number_pattern'] = invoice_pattern
                    print(f"Invoice number pattern: {invoice_pattern}")
        
        # Update vendor config
        self.vendors[vendor_name] = vendor_config
        self._save_config()
        print(f"\nVendor configuration for {vendor_name} has been saved.")
    
    def train_line_item_extraction(self, vendor_name, sample_pdf_path):
        """
        Train the system to extract line items from invoices for a specific vendor.
        
        Args:
            vendor_name: Name of the vendor
            sample_pdf_path: Path to a sample PDF from this vendor
        """
        from invoice_parser import InvoiceParser
        
        # Make sure vendor exists in config
        if vendor_name not in self.vendors:
            print(f"Vendor {vendor_name} not found. Please train basic invoice extraction first.")
            return
            
        vendor_config = self.vendors[vendor_name]
        
        # Create line item config if it doesn't exist
        if 'line_item_config' not in vendor_config:
            vendor_config['line_item_config'] = {}
            
        line_item_config = vendor_config['line_item_config']
        
        # Ask about extraction method
        print("\nHow should we extract line items from this vendor's invoices?")
        print("1. Table-based extraction (recommended for structured tables)")
        print("2. Pattern-based extraction (for text-based line items)")
        extraction_choice = input("Enter choice (1 or 2): ").strip()
        
        if extraction_choice == '1':
            line_item_config['extraction_method'] = 'table'
            self._train_table_extraction(vendor_name, sample_pdf_path, line_item_config)
        elif extraction_choice == '2':
            line_item_config['extraction_method'] = 'pattern'
            self._train_pattern_extraction(vendor_name, sample_pdf_path, line_item_config)
        else:
            print("Invalid choice. Defaulting to table-based extraction.")
            line_item_config['extraction_method'] = 'table'
            self._train_table_extraction(vendor_name, sample_pdf_path, line_item_config)
        
        # Save the updated configuration
        self._save_config()
        
    def _train_table_extraction(self, vendor_name, sample_pdf_path, line_item_config):
        """
        Train table-based line item extraction.
        
        Args:
            vendor_name: Name of the vendor
            sample_pdf_path: Path to a sample PDF from this vendor
            line_item_config: Dictionary to store line item extraction config
        """
        from invoice_parser import InvoiceParser
        
        # Create parser to extract sample tables
        temp_parser = InvoiceParser(self)
        
        # Extract tables from the first page
        tables = temp_parser.extract_sample_tables(sample_pdf_path, 0)
        
        if not tables:
            print("No tables found on the first page. Trying page 2...")
            tables = temp_parser.extract_sample_tables(sample_pdf_path, 1)
            
        if not tables:
            print("No tables found. Cannot train table extraction.")
            return
            
        # Display the tables found
        print("\nFound the following tables:")
        for i, table in enumerate(tables):
            print(f"\nTable {i+1}:")
            print(tabulate(table[:min(5, len(table))], tablefmt="grid"))
            if len(table) > 5:
                print("... (more rows not shown)")
        
        # Ask which table contains line items
        table_choice = input("\nWhich table contains the line items? Enter table number: ").strip()
        try:
            table_index = int(table_choice) - 1
            if table_index < 0 or table_index >= len(tables):
                print("Invalid table number. Using first table.")
                table_index = 0
        except ValueError:
            print("Invalid input. Using first table.")
            table_index = 0
            
        selected_table = tables[table_index]
        
        # Configure table settings
        print("\nConfiguring table extraction settings...")
        line_item_config['table_settings'] = {
            'vertical_strategy': 'text',
            'horizontal_strategy': 'text',
            'intersection_tolerance': 2
        }
        
        # Ask if the table has a header
        has_header = input("Does the table have a header row? (y/n): ").lower() == 'y'
        line_item_config['has_header'] = has_header
        
        # Identify columns
        if has_header and len(selected_table) > 0:
            print("\nHeader row:")
            header_row = selected_table[0]
            for i, cell in enumerate(header_row):
                print(f"{i}: {cell if cell else '[Empty]'}")
                
            # Map columns to fields
            column_map = {}
            
            part_num_col = input("\nWhich column contains the part/item number? (Enter column number or skip): ").strip()
            if part_num_col.isdigit() and int(part_num_col) < len(header_row):
                column_map['part_number'] = int(part_num_col)
                
            desc_col = input("Which column contains the item description? (Enter column number or skip): ").strip()
            if desc_col.isdigit() and int(desc_col) < len(header_row):
                column_map['original_description'] = int(desc_col)
                
            qty_col = input("Which column contains the quantity? (Enter column number or skip): ").strip()
            if qty_col.isdigit() and int(qty_col) < len(header_row):
                column_map['quantity'] = int(qty_col)
                
            unit_price_col = input("Which column contains the unit price? (Enter column number or skip): ").strip()
            if unit_price_col.isdigit() and int(unit_price_col) < len(header_row):
                column_map['unit_price'] = int(unit_price_col)
                
            total_price_col = input("Which column contains the total price? (Enter column number or skip): ").strip()
            if total_price_col.isdigit() and int(total_price_col) < len(header_row):
                column_map['total_price'] = int(total_price_col)
                
            # Store column mapping
            line_item_config['column_map'] = column_map
        else:
            # For tables without headers, ask user to identify column positions
            print("\nSample data row:")
            if len(selected_table) > 1:
                data_row = selected_table[1 if has_header else 0]
                for i, cell in enumerate(data_row):
                    print(f"{i}: {cell if cell else '[Empty]'}")
                    
                # Map columns to fields
                column_map = {}
                
                part_num_col = input("\nWhich column contains the part/item number? (Enter column number or skip): ").strip()
                if part_num_col.isdigit() and int(part_num_col) < len(data_row):
                    column_map['part_number'] = int(part_num_col)
                    
                desc_col = input("Which column contains the item description? (Enter column number or skip): ").strip()
                if desc_col.isdigit() and int(desc_col) < len(data_row):
                    column_map['original_description'] = int(desc_col)
                    
                qty_col = input("Which column contains the quantity? (Enter column number or skip): ").strip()
                if qty_col.isdigit() and int(qty_col) < len(data_row):
                    column_map['quantity'] = int(qty_col)
                    
                unit_price_col = input("Which column contains the unit price? (Enter column number or skip): ").strip()
                if unit_price_col.isdigit() and int(unit_price_col) < len(data_row):
                    column_map['unit_price'] = int(unit_price_col)
                    
                total_price_col = input("Which column contains the total price? (Enter column number or skip): ").strip()
                if total_price_col.isdigit() and int(total_price_col) < len(data_row):
                    column_map['total_price'] = int(total_price_col)
                    
                # Store column mapping
                line_item_config['column_map'] = column_map
            else:
                print("Not enough data rows to identify columns.")
                return
                
        # Set minimum number of columns for table detection
        line_item_config['min_columns'] = 3
        
        # Ask for a unique identifier for the item table
        print("\nOptional: Enter some text that uniquely identifies the line item table")
        print("(This helps distinguish it from other tables in the document)")
        identifier = input("Table identifier (or skip): ").strip()
        if identifier:
            line_item_config['table_identifier'] = identifier
            
        print("\nLine item table extraction configured successfully.")
        
    def _train_pattern_extraction(self, vendor_name, sample_pdf_path, line_item_config):
        """
        Train pattern-based line item extraction.
        
        Args:
            vendor_name: Name of the vendor
            sample_pdf_path: Path to a sample PDF from this vendor
            line_item_config: Dictionary to store line item extraction config
        """
        from invoice_parser import InvoiceParser
        
        # Create parser to extract sample text
        temp_parser = InvoiceParser(self)
        sample_text = temp_parser.extract_training_page(sample_pdf_path)
        
        if not sample_text:
            print("Failed to extract text from the sample PDF.")
            return
            
        # Display the sample text for reference
        print("\n" + "="*80)
        print("SAMPLE INVOICE TEXT")
        print("="*80)
        print(sample_text)
        print("="*80 + "\n")
        
        print("For pattern-based extraction, we need to identify how line items appear in the text.")
        print("Look at the sample text and find a complete line item entry.")
        
        # Ask for a sample line item
        print("\nCopy and paste a COMPLETE line item from the text above:")
        line_item_sample = input("Sample line item: ").strip()
        
        if not line_item_sample:
            print("No sample provided. Cannot train pattern extraction.")
            return
            
        print("\nNow we'll identify the different parts of the line item.")
        
        # Build a pattern with capture groups for each field
        pattern_parts = []
        
        # Part number
        part_num = input("\nHighlight and copy just the part/item number from your sample (or skip): ").strip()
        if part_num:
            pattern_parts.append(f"(?P<part_number>{re.escape(part_num)})")
        
        # Description
        description = input("\nHighlight and copy just the item description from your sample (or skip): ").strip()
        if description:
            pattern_parts.append(f"(?P<description>{re.escape(description)})")
        
        # Quantity
        quantity = input("\nHighlight and copy just the quantity from your sample (or skip): ").strip()
        if quantity:
            pattern_parts.append(f"(?P<quantity>{re.escape(quantity)})")
        
        # Unit price
        unit_price = input("\nHighlight and copy just the unit price from your sample (or skip): ").strip()
        if unit_price:
            pattern_parts.append(f"(?P<unit_price>{re.escape(unit_price)})")
        
        # Total price
        total_price = input("\nHighlight and copy just the total price from your sample (or skip): ").strip()
        if total_price:
            pattern_parts.append(f"(?P<total_price>{re.escape(total_price)})")
        
        # Build the full pattern
        if not pattern_parts:
            print("No fields identified. Cannot train pattern extraction.")
            return
            
        # Combine parts with flexible whitespace
        item_pattern_str = line_item_sample
        for part in pattern_parts:
            escaped_value = re.escape(part.split("(?P<")[1].split(">")[1].split(")")[0])
            item_pattern_str = item_pattern_str.replace(escaped_value, part)
            
        # Store the pattern
        line_item_config['item_pattern'] = item_pattern_str
        
        print("\nPattern created for line item extraction.")
        print(f"Pattern: {item_pattern_str}")
        
    def _build_pattern_from_sample(self, text_sample, value_pattern):
        """
        Build a regex pattern from a text sample and value pattern.
        
        Args:
            text_sample: Sample text containing the value
            value_pattern: Regex pattern for the value itself
            
        Returns:
            Complete regex pattern with capture group
        """
        try:
            # Find the value in the sample text
            value_match = re.search(value_pattern, text_sample)
            if not value_match:
                return None
                
            value = value_match.group(0)
            before, after = text_sample.split(value, 1)
            
            # Create a pattern with the context before and after
            # Use up to 20 chars before and after for context
            before_context = re.escape(before[-20:] if len(before) > 20 else before)
            after_context = re.escape(after[:20] if len(after) > 20 else after)
            
            # Build the final pattern with a capture group for the value
            pattern = f"{before_context}({value_pattern}){after_context}"
            
            return pattern
        except Exception as e:
            logger.error(f"Error building pattern: {str(e)}")
            return None
            
    def get_all_vendor_names(self):
        """
        Get list of all configured vendor names.
        
        Returns:
            List of vendor names
        """
        return list(self.vendors.keys())