"""Starter examples so the learner works before you've given any feedback.

label 1 = scam / phishing, 0 = safe. All names, numbers and domains are made up.
Your own feedback (and any dataset you import with train.py) is added on top.
"""

SCAM = [
    "Dear Customer, your SBI account will be BLOCKED within 30 minutes due to incomplete KYC. Verify immediately at "
    "http://sbi-kyc-verify.xyz/login and enter your account number and OTP to avoid suspension.",
    "We are hiring for work-from-home part-time job. Earn Rs 3000-8000 per day by liking YouTube videos. No experience "
    "needed. Pay a refundable registration fee of Rs 499. Contact HR on WhatsApp.",
    "CONGRATULATIONS!!! Your mobile number has won Rs 25,00,000 in the KBC Lucky Draw. To claim your prize, pay a "
    "processing fee to UPI ID kbcprize.claim@ybl and send your Aadhaar and bank details.",
    "IndiaPost: Your package could not be delivered due to an incomplete address. Update your address within 12 hours: "
    "https://bit.ly/3IndPst. A redelivery fee of Rs 25 applies.",
    "Dear Student, you are selected for the National Merit Scholarship of Rs 50,000. To release the amount, pay a "
    "verification fee and share your bank account number, IFSC and the OTP you receive.",
    "Your Netflix membership is on hold. We couldn't process your last payment. Update your card details within 24 "
    "hours at netflix-billing-update.com to avoid cancellation.",
    "Microsoft account unusual sign-in activity detected. Confirm your password immediately or your mailbox will be "
    "deleted: http://office365-verify-login.top/secure",
    "Income Tax Department: you are eligible for a refund of Rs 15,490. Submit your bank account and PAN details at "
    "incometax-refund-portal.in.net to receive it today.",
    "Hello dear, I am a US army doctor posted abroad. I want to send you a gift parcel worth $50,000. Pay the customs "
    "clearance fee and keep this confidential.",
    "Guaranteed 30% monthly returns! Invest in our crypto trading plan, double your money in 60 days, risk-free. "
    "Join our Telegram group now, limited slots.",
    "Your electricity connection will be disconnected tonight at 9:30 pm because your previous bill was not updated. "
    "Immediately contact our officer on 9876500000.",
    "Amazon: your order has been put on hold. Install the AnyDesk app so our support team can process your refund.",
    "Your Apple ID has been locked for security reasons. Click here to unlock your account and confirm your identity.",
    "Final notice: your PAN card will be deactivated. Update KYC now by sharing the OTP sent to your number.",
    "You have received a cashback of Rs 5,000 on PhonePe. Scan the QR code and enter your UPI PIN to receive the money.",
    "Urgent: your WhatsApp will expire today. Verify your account by sending the 6-digit code we just sent you.",
]

SAFE = [
    "Dear students, the CA2 internal assessment for BCA Semester V will be held from 10 November. The timetable is on "
    "the college notice board and official website.",
    "Your Amazon.in order #402-1234567 has shipped and will arrive on Thursday. Track your package in Your Orders.",
    "Your OTP for login is 482910. It is valid for 10 minutes. Never share your OTP with anyone. HDFC Bank will never "
    "ask for it.",
    "Hi team, reminder that our project review meeting is tomorrow at 11 am in Lab 3. Please bring your progress slides.",
    "Your Swiggy order from Domino's has been delivered. Total paid Rs 412. Rate your order to help us improve.",
    "IRCTC: Your ticket is booked. PNR 4512367890, Howrah to Asansol, Coach S3, Seat 42. Have a happy journey.",
    "[GitHub] A new pull request was opened in your repository scamshield-ai. Review the changes on GitHub.",
    "Your password was changed successfully. If you did this, you can ignore this email.",
    "Thanks for registering for the Hacktoberfest Fest on Saturday. Doors open at 10 am. See you there!",
    "Your monthly statement for September is ready. Log in to the official app to view it.",
    "Hi, sharing the notes from today's Java OOP class. Assignment 3 is due next Monday.",
    "Google Pay: you paid Rs 120 to Ramesh Tea Stall. UPI transaction reference 6201234.",
    "Welcome to the DEV community! Complete your profile and follow tags you're interested in.",
    "Your library book 'Database Systems' is due for return on 15 October. Please return it to the central library.",
    "Electricity bill for September: Rs 860, due on 20 October. Pay through the official app or website.",
    "Your Zomato refund of Rs 150 has been processed to your original payment method. It may take 5-7 days to reflect.",
]

SEED_EXAMPLES = [(1, t) for t in SCAM] + [(0, t) for t in SAFE]
