# V62 Leave Save + Phone Dark Theme Fix

Fixed:
1. Leave page crash
   - Manual leave saving no longer uses positional list assignment.
   - It now writes by column names and includes Status='Approved'.
   - Prevents pandas error: cannot set a row with mismatched columns.

2. Dark theme button visibility
   - Removed over-aggressive global white button text rule.
   - Button dark-theme fix is now scoped to phone-width dark theme only.
   - Laptop/light-theme button behavior is not forcibly changed.
