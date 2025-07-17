#!/usr/bin/env python3
"""
Resume processing script with better database connection management
"""
import logging
import sys
from datetime import datetime
from main import main

if __name__ == "__main__":
    print("=== Resuming Rider Correlation Processing ===")
    print("With improved database connection management")
    print(f"Starting at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        result = main()
        if result == 0:
            print("\n✅ Processing completed successfully!")
        else:
            print(f"\n❌ Processing failed with exit code: {result}")
    except KeyboardInterrupt:
        print("\n⏹️  Processing interrupted by user")
    except Exception as e:
        print(f"\n💥 Processing failed with error: {e}")
        logging.exception("Full traceback:")
        
    print(f"Finished at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")