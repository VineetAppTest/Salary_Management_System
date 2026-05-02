# V55 Special Impact Profile Only

Implemented product-flow correction:
- Payroll page is now Step 1 only: regular overall payroll calculation.
- Removed Special Impact Tools from Payroll page to avoid confusion.
- Employee Profile is Step 2: person-wise recalculation and special impact handling.
- Special Impact Tools remain only in Employee Profile.
- Employee Profile recalculation continues to feed into Payroll, Salary Summary, Final Excel and connected reports.
- Payroll report now clarifies that it reflects regular payroll plus individual profile recalculations.

Reason:
- Avoids accidental global application of special impact rules when user intended employee-specific recalculation.
