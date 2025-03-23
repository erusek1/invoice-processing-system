#!/usr/bin/env python3
"""
Item Database Module
------------------
Manages storage and analysis of line items from invoices.
"""

import os
import logging
import pandas as pd
from datetime import datetime, timedelta
import sqlite3
import json

logger = logging.getLogger(__name__)

class ItemDatabase:
    def __init__(self, excel_output="item_database.xlsx", db_path="items.db"):
        """
        Initialize the item database manager.
        
        Args:
            excel_output: Path to the Excel file for output
            db_path: Path to the SQLite database file
        """
        self.excel_output = excel_output
        self.db_path = db_path
        self.items = []
        self.conn = None
        
        # Initialize database if needed
        self._init_database()
        
        # Load existing items from database
        self._load_items()
        
    def _init_database(self):
        """Initialize the SQLite database with required tables."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            cursor = self.conn.cursor()
            
            # Create tables if they don't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT,
                    invoice_number TEXT,
                    vendor TEXT,
                    part_number TEXT,
                    original_description TEXT,
                    custom_description TEXT,
                    quantity REAL,
                    unit_price REAL,
                    total_price REAL,
                    entry_date TEXT
                )
            ''')
            
            # Create index for faster queries
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_part_number ON items (part_number)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_vendor ON items (vendor)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_date ON items (date)')
            
            self.conn.commit()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {str(e)}", exc_info=True)
            
    def _load_items(self):
        """Load existing items from database."""
        try:
            if self.conn:
                # Query for all items
                cursor = self.conn.cursor()
                cursor.execute('SELECT * FROM items')
                columns = [desc[0] for desc in cursor.description]
                
                # Convert to list of dicts
                rows = cursor.fetchall()
                self.items = []
                for row in rows:
                    item_dict = dict(zip(columns, row))
                    # Remove the internal id field
                    if 'id' in item_dict:
                        del item_dict['id']
                    self.items.append(item_dict)
                    
                logger.info(f"Loaded {len(self.items)} items from database")
            else:
                logger.warning("Database connection not available")
        except Exception as e:
            logger.error(f"Error loading items from database: {str(e)}", exc_info=True)
            
    def add_item(self, item_data):
        """
        Add a line item to the database.
        
        Args:
            item_data: Dictionary containing line item data
        """
        try:
            # Add entry timestamp
            item_data['entry_date'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Ensure all expected fields are present
            for field in ['date', 'invoice_number', 'vendor', 'part_number', 'original_description', 
                         'custom_description', 'quantity', 'unit_price', 'total_price']:
                if field not in item_data:
                    item_data[field] = '' if field in ['date', 'invoice_number', 'vendor', 'part_number', 
                                                     'original_description', 'custom_description'] else 0.0
            
            # Add to in-memory list
            self.items.append(item_data.copy())
            
            # Add to database
            if self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    INSERT INTO items 
                    (date, invoice_number, vendor, part_number, original_description, 
                     custom_description, quantity, unit_price, total_price, entry_date)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item_data.get('date', ''),
                    item_data.get('invoice_number', ''),
                    item_data.get('vendor', ''),
                    item_data.get('part_number', ''),
                    item_data.get('original_description', ''),
                    item_data.get('custom_description', ''),
                    item_data.get('quantity', 0.0),
                    item_data.get('unit_price', 0.0),
                    item_data.get('total_price', 0.0),
                    item_data.get('entry_date', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
                ))
                self.conn.commit()
        except Exception as e:
            logger.error(f"Error adding item to database: {str(e)}", exc_info=True)
            
    def update_custom_description(self, item_id, custom_description):
        """
        Update the custom description for an item.
        
        Args:
            item_id: Database ID of the item
            custom_description: New custom description
        """
        try:
            if self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    UPDATE items 
                    SET custom_description = ?
                    WHERE id = ?
                ''', (custom_description, item_id))
                self.conn.commit()
                
                # Also update in memory
                self._load_items()  # Reload all items to reflect changes
                
                logger.info(f"Updated custom description for item {item_id}")
                return True
            else:
                logger.warning("Database connection not available")
                return False
        except Exception as e:
            logger.error(f"Error updating custom description: {str(e)}", exc_info=True)
            return False
            
    def get_items_by_part_number(self, part_number):
        """
        Get all items with a specific part number.
        
        Args:
            part_number: Part number to search for
            
        Returns:
            List of matching items
        """
        matching_items = []
        try:
            if self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    SELECT * FROM items 
                    WHERE part_number = ?
                    ORDER BY date DESC
                ''', (part_number,))
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                for row in rows:
                    item_dict = dict(zip(columns, row))
                    matching_items.append(item_dict)
            else:
                # Fall back to in-memory search
                matching_items = [item for item in self.items if item.get('part_number') == part_number]
                
            return matching_items
        except Exception as e:
            logger.error(f"Error retrieving items by part number: {str(e)}", exc_info=True)
            return []
            
    def get_items_by_vendor(self, vendor):
        """
        Get all items from a specific vendor.
        
        Args:
            vendor: Vendor name to search for
            
        Returns:
            List of matching items
        """
        matching_items = []
        try:
            if self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    SELECT * FROM items 
                    WHERE vendor = ?
                    ORDER BY date DESC
                ''', (vendor,))
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                for row in rows:
                    item_dict = dict(zip(columns, row))
                    matching_items.append(item_dict)
            else:
                # Fall back to in-memory search
                matching_items = [item for item in self.items if item.get('vendor') == vendor]
                
            return matching_items
        except Exception as e:
            logger.error(f"Error retrieving items by vendor: {str(e)}", exc_info=True)
            return []
            
    def get_items_by_date_range(self, start_date, end_date):
        """
        Get all items within a date range.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            
        Returns:
            List of matching items
        """
        matching_items = []
        try:
            if self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    SELECT * FROM items 
                    WHERE date >= ? AND date <= ?
                    ORDER BY date DESC
                ''', (start_date, end_date))
                
                columns = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()
                
                for row in rows:
                    item_dict = dict(zip(columns, row))
                    matching_items.append(item_dict)
            else:
                # Fall back to in-memory search
                matching_items = [item for item in self.items 
                                 if item.get('date', '') >= start_date and item.get('date', '') <= end_date]
                
            return matching_items
        except Exception as e:
            logger.error(f"Error retrieving items by date range: {str(e)}", exc_info=True)
            return []
            
    def get_recent_items(self, days=30):
        """
        Get items from the last N days.
        
        Args:
            days: Number of days to look back
            
        Returns:
            List of recent items
        """
        # Calculate the date N days ago
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
        
        return self.get_items_by_date_range(start_date, end_date)
    
    def get_price_history(self, part_number):
        """
        Get the price history for a specific part.
        
        Args:
            part_number: Part number to get history for
            
        Returns:
            List of (date, price) tuples sorted by date
        """
        price_history = []
        try:
            if self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    SELECT date, unit_price 
                    FROM items 
                    WHERE part_number = ?
                    ORDER BY date ASC
                ''', (part_number,))
                
                price_history = cursor.fetchall()
            else:
                # Fall back to in-memory search
                matching_items = [item for item in self.items if item.get('part_number') == part_number]
                price_history = [(item.get('date', ''), item.get('unit_price', 0.0)) for item in matching_items]
                price_history.sort(key=lambda x: x[0])  # Sort by date
                
            return price_history
        except Exception as e:
            logger.error(f"Error retrieving price history: {str(e)}", exc_info=True)
            return []
    
    def find_lowest_price_vendor(self, part_number):
        """
        Find the vendor with the lowest price for a specific part.
        
        Args:
            part_number: Part number to check
            
        Returns:
            Dictionary with vendor and price information
        """
        try:
            if self.conn:
                cursor = self.conn.cursor()
                cursor.execute('''
                    SELECT vendor, MIN(unit_price) as min_price, date
                    FROM items
                    WHERE part_number = ?
                    GROUP BY vendor
                    ORDER BY min_price ASC
                ''', (part_number,))
                
                results = cursor.fetchall()
                
                if results:
                    return {
                        'part_number': part_number,
                        'best_vendor': results[0][0],
                        'best_price': results[0][1],
                        'best_price_date': results[0][2],
                        'all_vendors': [{'vendor': r[0], 'price': r[1], 'date': r[2]} for r in results]
                    }
            else:
                # Fall back to in-memory analysis
                matching_items = [item for item in self.items if item.get('part_number') == part_number]
                if matching_items:
                    # Group by vendor and find min price
                    vendor_prices = {}
                    vendor_dates = {}
                    for item in matching_items:
                        vendor = item.get('vendor', '')
                        price = item.get('unit_price', 0.0)
                        date = item.get('date', '')
                        
                        if vendor not in vendor_prices or price < vendor_prices[vendor]:
                            vendor_prices[vendor] = price
                            vendor_dates[vendor] = date
                    
                    # Find best vendor
                    best_vendor = min(vendor_prices, key=vendor_prices.get)
                    
                    return {
                        'part_number': part_number,
                        'best_vendor': best_vendor,
                        'best_price': vendor_prices[best_vendor],
                        'best_price_date': vendor_dates[best_vendor],
                        'all_vendors': [{'vendor': v, 'price': p, 'date': vendor_dates[v]} 
                                      for v, p in vendor_prices.items()]
                    }
            
            return None
        except Exception as e:
            logger.error(f"Error finding lowest price vendor: {str(e)}", exc_info=True)
            return None
    
    def find_price_changes(self, threshold_percent=5, days=90):
        """
        Find parts with significant price changes.
        
        Args:
            threshold_percent: Minimum percentage change to report
            days: Number of days to look back
            
        Returns:
            List of items with significant price changes
        """
        significant_changes = []
        try:
            # Get parts with data in the last N days
            recent_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            if self.conn:
                cursor = self.conn.cursor()
                
                # Find distinct part numbers with recent data
                cursor.execute('''
                    SELECT DISTINCT part_number
                    FROM items
                    WHERE date >= ?
                ''', (recent_date,))
                
                part_numbers = [row[0] for row in cursor.fetchall()]
                
                # For each part number, check price changes
                for part_number in part_numbers:
                    cursor.execute('''
                        SELECT date, unit_price, vendor
                        FROM items
                        WHERE part_number = ?
                        ORDER BY date ASC
                    ''', (part_number,))
                    
                    price_history = cursor.fetchall()
                    
                    if len(price_history) >= 2:
                        oldest_price = price_history[0][1]
                        newest_price = price_history[-1][1]
                        
                        if oldest_price > 0:  # Avoid division by zero
                            percent_change = ((newest_price - oldest_price) / oldest_price) * 100
                            
                            if abs(percent_change) >= threshold_percent:
                                # Find description
                                cursor.execute('''
                                    SELECT original_description, custom_description
                                    FROM items
                                    WHERE part_number = ?
                                    ORDER BY date DESC
                                    LIMIT 1
                                ''', (part_number,))
                                
                                desc_row = cursor.fetchone()
                                description = desc_row[1] if desc_row[1] else desc_row[0]
                                
                                significant_changes.append({
                                    'part_number': part_number,
                                    'description': description,
                                    'old_price': oldest_price,
                                    'old_date': price_history[0][0],
                                    'new_price': newest_price,
                                    'new_date': price_history[-1][0],
                                    'percent_change': percent_change,
                                    'vendor': price_history[-1][2]
                                })
            else:
                # Fall back to in-memory analysis
                # This implementation is simplified compared to the SQL version
                part_prices = {}
                
                for item in self.items:
                    part_number = item.get('part_number', '')
                    if not part_number:
                        continue
                        
                    date = item.get('date', '')
                    price = item.get('unit_price', 0.0)
                    vendor = item.get('vendor', '')
                    description = item.get('custom_description', '') or item.get('original_description', '')
                    
                    if part_number not in part_prices:
                        part_prices[part_number] = {
                            'prices': [],
                            'description': description
                        }
                        
                    part_prices[part_number]['prices'].append((date, price, vendor))
                
                # Check for significant changes
                for part_number, data in part_prices.items():
                    prices = sorted(data['prices'], key=lambda x: x[0])  # Sort by date
                    
                    if len(prices) >= 2:
                        oldest_price = prices[0][1]
                        newest_price = prices[-1][1]
                        
                        if oldest_price > 0:  # Avoid division by zero
                            percent_change = ((newest_price - oldest_price) / oldest_price) * 100
                            
                            if abs(percent_change) >= threshold_percent:
                                significant_changes.append({
                                    'part_number': part_number,
                                    'description': data['description'],
                                    'old_price': oldest_price,
                                    'old_date': prices[0][0],
                                    'new_price': newest_price,
                                    'new_date': prices[-1][0],
                                    'percent_change': percent_change,
                                    'vendor': prices[-1][2]
                                })
            
            # Sort by absolute percentage change (largest first)
            significant_changes.sort(key=lambda x: abs(x['percent_change']), reverse=True)
            return significant_changes
        except Exception as e:
            logger.error(f"Error finding price changes: {str(e)}", exc_info=True)
            return []
    
    def export_for_llm(self, output_path="llm_data.json"):
        """
        Export data in a format suitable for LLM analysis.
        
        Args:
            output_path: Path to save the JSON output
            
        Returns:
            Path to the output file or None if failed
        """
        try:
            # Prepare the data structure
            export_data = {
                'items': self.items,
                'price_changes': self.find_price_changes(),
                'export_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'summary': {
                    'total_items': len(self.items),
                    'unique_parts': len(set(item.get('part_number', '') for item in self.items)),
                    'vendors': list(set(item.get('vendor', '') for item in self.items))
                }
            }
            
            # Create vendor comparison data
            vendor_comparison = {}
            for item in self.items:
                part_number = item.get('part_number', '')
                if not part_number:
                    continue
                    
                vendor = item.get('vendor', '')
                price = item.get('unit_price', 0.0)
                date = item.get('date', '')
                
                if part_number not in vendor_comparison:
                    vendor_comparison[part_number] = {}
                    
                if vendor not in vendor_comparison[part_number]:
                    vendor_comparison[part_number][vendor] = []
                    
                vendor_comparison[part_number][vendor].append({
                    'price': price,
                    'date': date
                })
            
            # Add vendor comparison to export data
            export_data['vendor_comparison'] = vendor_comparison
            
            # Write to file
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2)
                
            logger.info(f"Data exported to {output_path}")
            return output_path
        except Exception as e:
            logger.error(f"Error exporting data for LLM: {str(e)}", exc_info=True)
            return None
    
    def save(self):
        """Save the database to Excel."""
        try:
            if not self.items:
                logger.warning("No items to save to Excel")
                return
                
            # Convert to DataFrame
            df = pd.DataFrame(self.items)
            
            # Save to Excel
            df.to_excel(self.excel_output, index=False)
            logger.info(f"Item database saved to {self.excel_output}")
            
            # Make sure database connection is committed
            if self.conn:
                self.conn.commit()
        except Exception as e:
            logger.error(f"Error saving item database: {str(e)}", exc_info=True)
    
    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None