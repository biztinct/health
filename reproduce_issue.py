
# Script to reproduce/verify access permission issue
# Run with: python3 reproduce_issue.py

import unittest
from unittest.mock import MagicMock

# Mock Odoo environment
class MockUser:
    def __init__(self, id, name):
        self.id = id
        self.name = name

class MockRecord:
    def __init__(self, id, **kwargs):
        self.id = id
        for k, v in kwargs.items():
            setattr(self, k, v)

# Simplified logic of the domain
def check_access(user, order):
    # Domain logic:
    # '|', '|', '|',
    # ('assignment_ids.staff_id.user_id', '=', user.id),
    # ('primary_doctor_id.user_id', '=', user.id),
    # ('primary_nurse_id.user_id', '=', user.id),
    # ('created_by_employee_id.user_id', '=', user.id)
    
    # Check assignment_ids
    assigned = False
    if hasattr(order, 'assignment_ids'):
        for assignment in order.assignment_ids:
            if assignment.staff_id.user_id.id == user.id:
                assigned = True
                break
    
    # Check primary doctor
    is_primary_doctor = False
    if hasattr(order, 'primary_doctor_id') and order.primary_doctor_id:
        if order.primary_doctor_id.user_id.id == user.id:
            is_primary_doctor = True
            
    # Check primary nurse
    is_primary_nurse = False
    if hasattr(order, 'primary_nurse_id') and order.primary_nurse_id:
        if order.primary_nurse_id.user_id.id == user.id:
            is_primary_nurse = True

    # Check created_by
    is_creator = False
    if hasattr(order, 'created_by_employee_id') and order.created_by_employee_id:
        if order.created_by_employee_id.user_id.id == user.id:
            is_creator = True
            
    return assigned or is_primary_doctor or is_primary_nurse or is_creator

class TestAccessRules(unittest.TestCase):
    def setUp(self):
        self.user = MockUser(14, "Lan Nurse")
        self.other_user = MockUser(99, "Other User")
        
        self.staff_employee = MockRecord(100, user_id=self.user)
        self.other_employee = MockRecord(101, user_id=self.other_user)
        
    def test_assigned_access(self):
        # Case 1: User is assigned
        assignment = MockRecord(1, staff_id=self.staff_employee)
        order = MockRecord(1, assignment_ids=[assignment])
        self.assertTrue(check_access(self.user, order), "Assigned user should have access")

    def test_primary_doctor_access(self):
        # Case 2: User is primary doctor
        order = MockRecord(2, primary_doctor_id=self.staff_employee)
        self.assertTrue(check_access(self.user, order), "Primary doctor should have access")

    def test_primary_nurse_access(self):
        # Case 3: User is primary nurse
        order = MockRecord(3, primary_nurse_id=self.staff_employee)
        self.assertTrue(check_access(self.user, order), "Primary nurse should have access")
        
    def test_creator_access(self):
        # Case 4: User is creator (The Fix)
        order = MockRecord(4, created_by_employee_id=self.staff_employee)
        self.assertTrue(check_access(self.user, order), "Creator should have access")
        
    def test_no_access(self):
        # Case 5: User has no relation
        order = MockRecord(5, 
            assignment_ids=[], 
            primary_doctor_id=self.other_employee,
            primary_nurse_id=self.other_employee,
            created_by_employee_id=self.other_employee
        )
        self.assertFalse(check_access(self.user, order), "Unrelated user should NOT have access")

if __name__ == '__main__':
    unittest.main()
