
# Stats service for tracking domain generation statistics

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import Depends
from ..models import StatsCounter
from ..database import get_db
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StatsService:
    def __init__(self, db: Session = Depends(get_db)):
        self.db = db
    
    async def increment_counter(self, counter_name: str, increment_by: int = 1):
        """Increment a counter by the specified amount"""
        try:
            # Try to get the counter first
            counter = self.db.query(StatsCounter).filter(StatsCounter.counter_name == counter_name).first()
            
            if counter:
                # Counter exists, increment it
                counter.counter_value += increment_by
            else:
                # Counter doesn't exist, create it
                counter = StatsCounter(counter_name=counter_name, counter_value=increment_by)
                self.db.add(counter)
            
            self.db.commit()
            logger.info(f"Incremented counter '{counter_name}' by {increment_by}, new value: {counter.counter_value}")
            return counter.counter_value
        
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error incrementing counter: {str(e)}")
            return None
    
    async def get_counter_value(self, counter_name: str):
        """Get the current value of a counter"""
        try:
            counter = self.db.query(StatsCounter).filter(StatsCounter.counter_name == counter_name).first()
            return counter.counter_value if counter else 0
        
        except SQLAlchemyError as e:
            logger.error(f"Error getting counter value: {str(e)}")
            return 0
    
    async def reset_counter(self, counter_name: str):
        """Reset a counter to zero"""
        try:
            counter = self.db.query(StatsCounter).filter(StatsCounter.counter_name == counter_name).first()
            if counter:
                counter.counter_value = 0
                self.db.commit()
                logger.info(f"Reset counter '{counter_name}' to 0")
                return True
            return False
        
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error resetting counter: {str(e)}")
            return False 