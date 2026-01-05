# Bulk Upload Formats

This document describes the required format for bulk uploading students, teachers, and store staff to the Academy Program system.

## Overview

The admin dashboard supports bulk upload of user data via CSV or Excel (.xlsx) files. Each type of user has specific required and optional fields.

---

## Student Upload Format

### Required Columns

| Column Name | Type | Description | Example |
|-------------|------|-------------|---------|
| `full_name` | String | Student's full name | Ahmed Mohammed Al-Rashid |
| `email` | String | Valid email address (must be unique) | ahmed.rashid@academy.edu |
| `phone_number` | String | Phone number | +966501234567 |

### Optional Columns

| Column Name | Type | Description | Default | Example |
|-------------|------|-------------|---------|---------|
| `phone` | String | Phone number with country code | Empty | +966501234567 |
| `date_of_birth` | Date | Birth date (YYYY-MM-DD format) | Empty | 2000-05-15 |
| `gender` | String | M or F | Empty | M |
| `emergency_contact` | String | Emergency contact name | Empty | Mohammed Al-Rashid |
| `emergency_phone` | String | Emergency contact phone | Empty | +966507654321 |
| `address` | String | Home address | Empty | Riyadh, Saudi Arabia |
| `blood_type` | String | Blood type | Empty | A+ |
| `notes` | String | Additional notes | Empty | Allergies: None |

### Sample CSV

```csv
full_name,email,phone_number,phone,date_of_birth,gender
Ahmed Mohammed Al-Rashid,ahmed.rashid@academy.edu,1234567890,+966501234567,2000-05-15,M
Sara Abdullah Al-Qahtani,sara.qahtani@academy.edu,1234567891,+966502345678,2001-03-22,F
Omar Hassan Al-Otaibi,omar.otaibi@academy.edu,1234567892,+966503456789,1999-11-08,M
```

### Notes for Student Upload
- The **program** is selected in the upload interface (not in the file)
- Email addresses must be unique across all users
- National ID must be unique
- A temporary password will be generated for each student
- Students will be marked as active by default

---

## Teacher Upload Format

### Required Columns

| Column Name | Type | Description | Example |
|-------------|------|-------------|---------|
| `full_name` | String | Teacher's full name | Dr. Khalid Ibrahim |
| `email` | String | Valid email address (must be unique) | khalid.ibrahim@academy.edu |
| `employee_id` | String | Employee ID number | EMP-001 |
| `department` | String | Department name | Computer Science |

### Optional Columns

| Column Name | Type | Description | Default | Example |
|-------------|------|-------------|---------|---------|
| `phone` | String | Phone number with country code | Empty | +966504567890 |
| `title` | String | Academic title | Empty | Professor |
| `specialization` | String | Area of expertise | Empty | Machine Learning |
| `office_location` | String | Office building/room | Empty | Building A, Room 201 |
| `hire_date` | Date | Date of hire (YYYY-MM-DD) | Today | 2020-09-01 |
| `notes` | String | Additional notes | Empty | Office hours: Sun-Thu 10-12 |

### Sample CSV

```csv
full_name,email,employee_id,department,title,phone
Dr. Khalid Ibrahim,khalid.ibrahim@academy.edu,EMP-001,Computer Science,Professor,+966504567890
Dr. Fatima Al-Saud,fatima.alsaud@academy.edu,EMP-002,Mathematics,Associate Professor,+966505678901
Eng. Yousef Al-Ghamdi,yousef.ghamdi@academy.edu,EMP-003,Engineering,Lecturer,+966506789012
```

### Notes for Teacher Upload
- The **program assignment** is selected in the upload interface
- Employee IDs must be unique
- A temporary password will be generated for each teacher
- Teachers will be marked as active by default

---

## Store Staff Upload Format

### Required Columns

| Column Name | Type | Description | Example |
|-------------|------|-------------|---------|
| `full_name` | String | Staff member's full name | Ali Hassan |
| `email` | String | Valid email address (must be unique) | ali.hassan@academy.edu |
| `employee_id` | String | Employee ID number | STF-001 |

### Optional Columns

| Column Name | Type | Description | Default | Example |
|-------------|------|-------------|---------|---------|
| `phone` | String | Phone number | Empty | +966507890123 |
| `role_level` | String | Staff role level | cashier | cashier, supervisor, manager |
| `shift` | String | Work shift | morning | morning, afternoon, night |
| `notes` | String | Additional notes | Empty | Trained on POS system |

### Sample CSV

```csv
full_name,email,employee_id,phone,role_level,shift
Ali Hassan,ali.hassan@academy.edu,STF-001,+966507890123,cashier,morning
Noura Abdullah,noura.abdullah@academy.edu,STF-002,+966508901234,supervisor,afternoon
Mohammed Khalid,mohammed.khalid@academy.edu,STF-003,+966509012345,cashier,morning
```

### Notes for Store Staff Upload
- Staff will be assigned to the store/meal service
- A temporary password will be generated for each staff member
- Staff will be marked as active by default

---

## Excel Format Notes

When using Excel (.xlsx) files:

1. **Sheet Name**: Data should be in the first sheet
2. **Header Row**: First row must contain column headers exactly as specified
3. **Encoding**: UTF-8 encoding is recommended for Arabic names
4. **Date Format**: Use YYYY-MM-DD format or Excel date format
5. **No Merged Cells**: Avoid merged cells in the data area
6. **No Formulas**: Use values only, not formulas

---

## Common Errors and Solutions

### Duplicate Email Error
**Error**: "Email already exists"
**Solution**: Ensure each email is unique. Check for duplicates in your file and against existing users.

### Invalid Email Format
**Error**: "Invalid email format"
**Solution**: Ensure emails follow the format: username@domain.tld

### Missing Required Field
**Error**: "Required field missing: [field_name]"
**Solution**: Ensure all required columns are present and have values for each row.

### Invalid Date Format
**Error**: "Invalid date format"
**Solution**: Use YYYY-MM-DD format (e.g., 2000-05-15)

### File Too Large
**Error**: "File size exceeds limit"
**Solution**: Split the file into smaller batches (recommended: 500 rows per file)

---

## Best Practices

1. **Validate Before Upload**: Review your data for completeness and accuracy
2. **Start Small**: Test with a small batch (5-10 records) before bulk upload
3. **Backup**: Keep a backup of your original file
4. **Check Results**: After upload, verify users were created correctly
5. **Clean Data**: Remove extra spaces, fix capitalization, standardize phone formats

---

## Download Templates

Templates can be downloaded directly from the Bulk Upload page in the admin dashboard:

- [Student Template](/#) - Download from dashboard
- [Teacher Template](/#) - Download from dashboard
- [Store Staff Template](/#) - Download from dashboard

---

## Support

For assistance with bulk uploads, contact the system administrator or refer to the admin dashboard help section.
