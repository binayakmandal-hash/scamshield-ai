"""Hand-written evaluation cases for the safety tools.

These were written AFTER the rules, by the same author, so they are not an independent test set:
expect real-world accuracy to be lower. They try to vary the wording (Hinglish, typos, short replies,
genuine look-alikes) instead of copying the rule patterns.

Batch 1 found three bugs in the UPI check, which were fixed, so batch 1 is no longer a fair test.
Batch 2 (HELDOUT_*) was written afterwards and has never been used to change the rules; its numbers
are the ones to quote. See docs/EVALUATION.md.
"""

# (label, chat). label = script id from services/scam_scripts.py, or "none" for a normal chat.
CHATS = [
    ("task_scam", """Anjali: Hi dear, are you interested in a part time job? You can earn 2000-5000 per day
Me: what do I have to do
Anjali: simple tasks, just like and subscribe youtube channels and send screenshot
Me: ok done
Anjali: Your commission credited Rs 210, please check
Anjali: For VIP tasks you must join our telegram channel, contact receptionist @mira_hr"""),
    ("task_scam", """HR Team: Hotel review job, rate hotels on google maps, earn ₹150 per review
Me: sounds good
HR Team: we paid you rs 450 for 3 reviews
HR Team: Now merchant tasks: invest Rs 5000, get Rs 6500 back
Me: I paid 5000
HR Team: your account shows negative balance, recharge Rs 12000 to withdraw your earnings"""),
    ("task_scam", """Mentor: Congrats on completing level 1. To withdraw your profit you need to pay income tax on your earnings, 18% GST
Me: but I already paid 3 times
Mentor: Your account is frozen, pay one more time to unfreeze. Credit score low"""),
    ("kyc_expiry", """+91 7865xxxxxx: Dear customer your SBI YONO KYC has expired, account will be blocked today. Update now http://sbi-yono-kyc.in/update
Me: what is this
+91 7865xxxxxx: Sir quickly fill the form and share OTP received on mobile"""),
    ("kyc_expiry", """Paytm Care: Your Paytm wallet will be suspended within 24 hours. Pan card not linked.
Paytm Care: Download the update app and complete KYC: paytm-kyc.apk
Paytm Care: enter your card number and CVV for verification"""),
    ("digital_arrest", """Customs Officer: Mrs Gupta, a parcel to Taiwan in your name was seized with MDMA drugs.
Customs Officer: Connecting you to Mumbai police cyber cell.
Inspector: Your Aadhaar was used in money laundering. Case is registered.
Inspector: You are under digital arrest. Stay on Skype camera, don't inform your family, it is confidential."""),
    ("digital_arrest", """TRAI: your number will be disconnected in 2 hours due to illegal activity
CBI officer: An arrest warrant is issued in your name for hawala
CBI officer: To clear your name transfer your funds to the RBI secure account. It is refundable after verification"""),
    ("investment", """Admin: Welcome to VIP stock tips group by SEBI registered advisor. Guaranteed 300% returns in IPO
Member Rakesh: Thank you sir, made profit of ₹48,000 today
Member Sita: thanks teacher, returns credited
Admin: Download our institutional trading app and deposit minimum 10000"""),
    ("investment", """Riya: I learned crypto trading from my uncle, 20% profit daily
Riya: see these screenshots of my profit
Riya: register on the trading platform, deposit 25000 to start
Me: I want to withdraw now
Riya: you have to pay withdrawal tax 30% first, otherwise account is locked"""),
    ("job_fee", """TCS Recruitment: Congratulations! You are selected for the post of Data Entry Operator. No interview needed.
TCS Recruitment: Pay Rs 2,500 refundable security deposit for your offer letter and joining kit"""),
    ("job_fee", """Amazon HR: You are shortlisted for work from warehouse job, salary 32000
Amazon HR: registration fee Rs 999 must be paid today
Me: paid
Amazon HR: now pay the laptop charge and insurance fee of 4500"""),
    ("parcel", """India Post: Your parcel is on hold due to incomplete address. Update within 12 hours: https://indiapost-redelivery.top
Me: ok
India Post: Pay redelivery fee Rs 25 on the page using your card details"""),
    ("parcel", """DTDC: delivery attempt failed for AWB 77812. Click to reschedule http://dtdc-help.co
DTDC: a small customs charge of Rs 49 is pending"""),
    ("electricity", """Dear consumer, your electricity power will be disconnected tonight at 9.30 pm because your previous month bill was not updated. Please immediately contact our electricity officer 9832xxxxxx
Me: hello I paid the bill
Officer: Sir install AnyDesk app from Play Store, I will update it
Officer: Now pay Rs 10 to check"""),
    ("electricity", """WBSEDCL: Bijli connection will be cut today. Call our officer 7003xxxxxx
Officer: Download Quick Support app, share the code"""),
    ("prize", """KBC Lottery: Congratulations! Your number won 25 lakh in Kaun Banega Crorepati lucky draw
Mr Rana Pratap: To receive the prize pay processing fee Rs 15,500
Me: sent
Mr Rana Pratap: now RBI clearance charge and income tax required"""),
    ("prize", """Winner! You have been selected for an iPhone 16 gift in Flipkart Big Billion lucky draw. Pay delivery charge Rs 499 to claim"""),
    ("marketplace_qr", """Capt. Vikram: Hello I am interested in your bike on OLX. I am army officer, CISF, being transferred to Pune
Capt. Vikram: I will pay full amount without seeing. Our army accountant will send a QR code
Capt. Vikram: Scan the QR and enter your UPI PIN to receive the money
Me: it deducted 15000 from my account
Capt. Vikram: Sorry sent by mistake, scan again for refund"""),
    ("marketplace_qr", """Buyer: Is the fridge still available? I want to buy your fridge, I'll send collect request, just approve to receive payment"""),
    # Normal chats, including look-alikes of real messages.
    ("none", """Rahul: bro are we meeting at 7?
Me: yes, at the cafe near metro
Rahul: cool, I'll book the table"""),
    ("none", """Maa: Did you eat?
Me: yes
Maa: Call papa when you are free, he wants to talk about the electricity bill, he paid it online today"""),
    ("none", """Neha (Recruiter, Infosys): Hi, I came across your LinkedIn profile. We have an opening for a Python developer.
Me: I'm interested
Neha (Recruiter, Infosys): Great, I'll share the interview slots for next week. Please apply on the careers page as well."""),
    ("none", """Landlord: Rent for October is due on the 5th
Me: Will transfer by UPI tomorrow
Landlord: ok thanks"""),
    ("none", """Amazon: Your order of Boat Earbuds has been shipped and will be delivered by Thursday. Track in the Amazon app."""),
    ("none", """Priya: Can you send me 500 for the movie tickets? I paid for both
Me: sure sending on gpay
Priya: got it thanks"""),
    ("none", """HDFC Bank: Rs 2,450 spent on your credit card ending 4521 at SWIGGY on 12-10-26. Not you? Call 1800 202 6161"""),
    ("none", """Sir: Tomorrow's class is cancelled. Submit the assignment on Google Classroom by Friday."""),
    ("none", """Courier boy: Sir I am outside your gate with the parcel, please come down
Me: coming"""),
    ("none", """Dad: The police verification for the passport is tomorrow at 11, keep your documents ready
Me: ok"""),
    ("none", """Friend: I started investing in index funds through Zerodha, it's slow but steady. You should look at SIPs
Me: will check"""),
]

# (expected verdict, text). Verdicts: danger | caution | info | none
UPI = [
    ("danger", "Rahul Sharma has requested ₹3,500 from you. Approve the request to receive your refund."),
    ("danger", "You have received a cashback of Rs 1999 from PhonePe. Enter UPI PIN to claim the amount."),
    ("danger", "Payment request from cashback.offer@ybl for Rs 999. Approve to get reward. Expires in 5 min"),
    ("danger", "bhai galti se 2000 transfer ho gaya aapke account me, please return the money, mera UPI 98300xxxxx@paytm"),
    ("danger", "Sir I sent you Rs 10,000 by mistake, kindly send back the extra amount to rohit.k@okicici"),
    ("danger", "Your Amazon refund is ready. Scan this QR to receive Rs 2,349 in your account."),
    ("danger", "Flipkart Support: To get your refund of Rs 1,250 pay Rs 1 to 7003456789@ybl and enter your UPI PIN"),
    ("danger", "OLX buyer: I'm sending a collect request of 8000, accept it and enter PIN to get the payment"),
    ("danger", "Electricity board: pay Rs 10 to update your bill, install AnyDesk first so our officer can help"),
    ("danger", "Congratulations you won KBC prize! Pay Rs 4,500 processing fee to kbc.claim@axl to release your prize"),
    ("caution", "Pay Rs 450 to raju.tea@okaxis for the order"),
    ("caution", "Kiran Traders has requested Rs 1,200 for invoice 556 on Google Pay"),
    ("caution", "upi://pay?pa=sharma.kirana@okhdfcbank&pn=Sharma%20Kirana&am=320&cu=INR"),
    ("caution", "Please pay the society maintenance Rs 2500 to rwa.greenpark@sbi"),
    ("info", "Rs 5,000.00 credited to your A/c XX1234 on 12-10-26 by UPI ref 428612345678. -SBI"),
    ("info", "Your account has been credited with INR 1,500 from Priya Das. Avl bal Rs 12,340"),
    ("info", "Money received! ₹750 from Amit has been credited to your bank account"),
    ("none", "Hi, are you coming to the meeting today?"),
    ("none", "Please share your resume at hr@company.com"),
    ("none", "Your OTP for login is 482910. Do not share it with anyone. - ICICI Bank"),
]

# (label, transcript). label: "scam" or "safe". A call is predicted "scam" when the copilot reaches its
# "warning" or "scam" level (the page shows a warning at that point).
CALLS = [
    ("scam", "Hello madam, I am calling from Mumbai crime branch. Your Aadhaar is linked to money laundering. Do not tell anyone about this call."),
    ("scam", "Sir this is SBI customer care, your account will be blocked today. Please tell me the OTP you just received."),
    ("scam", "Please install AnyDesk app so I can help you get your refund, then open your bank app."),
    ("scam", "Papa, I had an accident, I'm at the police station, please send money urgently and don't tell mummy."),
    ("scam", "Your SIM will be deactivated in two hours. Press 9 to speak to TRAI officer. Stay on the call."),
    ("scam", "You have won a lottery of 25 lakh. To receive the prize money pay the GST via Google Play card."),
    ("scam", "This is customs department. Your parcel has drugs. Transfer your savings to the RBI verification account, it will be refunded after investigation."),
    ("scam", "Ma'am I am from Flipkart, your refund is pending, scan the QR code I sent on WhatsApp to receive the money."),
    ("scam", "I am calling from your bank, please share your card number and expiry date to stop the fraud transaction."),
    ("scam", "Narcotics department speaking, a FIR is registered in your name. Keep your camera on and do not disconnect the call."),
    ("scam", "Sir your electricity connection will be disconnected tonight. Download this app and share the code with me."),
    ("scam", "Your KYC is pending, your account will be suspended. Tell me the code sent to your phone to verify."),
    ("safe", "Hi beta, I reached home safely. The train was late but it's fine. Call me after your class."),
    ("safe", "Hello, this is Dr. Mehta's clinic confirming your appointment tomorrow at 10 am."),
    ("safe", "Sir your Swiggy order is outside, I am at the gate."),
    ("safe", "Hi, this is Neha from the HR team at Infosys, can we schedule your interview for Monday?"),
    ("safe", "Hey, are you coming to the cricket match on Sunday? Bring your bat."),
    ("safe", "Good morning, this is a reminder from your school that the parent teacher meeting is on Saturday."),
    ("safe", "Bhaiya, mummy is asking whether you will come home for Diwali this year."),
    ("safe", "Hello, I'm calling from the electricity office, the meter reading for your area will be taken tomorrow."),
]

# --------------------------------------------------------------------------- #
# Second batch, written after the first run and never used to change the rules.
# Its first-run numbers are the ones reported as "held-out" in docs/EVALUATION.md.
# --------------------------------------------------------------------------- #
HELDOUT_CHATS = [
    ("task_scam", """Sneha: hii, home based job available, daily payout 3k-8k, interested?
Me: yes
Sneha: task 1 follow this insta page and send ss. you got Rs 120 bonus
Sneha: next is prepaid task, pay 2000 get 2800. pls deposit in this acc"""),
    ("task_scam", """Telegram receptionist: complete combination task to continue, your balance is negative now, top up 8,500"""),
    ("kyc_expiry", """BOB: Dear user your account will be deactivated today pls update KYC immediately by clicking the link bit.ly/bob-kyc"""),
    ("digital_arrest", """Caller (ED): You are suspect in a money laundering case. Jet Airways founder case. You can't tell anyone, national secret. Keep your video on.
Caller (ED): Break your FD and transfer to the government account for verification"""),
    ("investment", """Prof. Arjun Mehta's stock group: today's IPO allotment guaranteed, 400% returns. Members already booked profit. Use our app to buy, min deposit 50k"""),
    ("job_fee", """Wipro HR: offer letter attached, joining date 1 Nov. Kindly pay documentation charge of Rs 1500 to confirm"""),
    ("parcel", """FedEx: your shipment is held at customs. Pay customs fee 150 rupees here: fedex-in-pay.xyz"""),
    ("electricity", """Dear Customer, Ur Electricity Power Will be Disconnect Tonight 9:30 PM. Becoz Your last Month Bill was Not Update. Plz Contact Our Officer 8293xxxxxx"""),
    ("prize", """Jio: Congratulations!! You are the winner of Jio lucky draw 2026, prize 12 lakh. Pay registration fee 7500 rs"""),
    ("marketplace_qr", """Hi I saw your sofa on marketplace, I'll take it. I'm in army, can't come. Sending QR, scan it to receive the amount"""),
    ("none", """Bank of Baroda: Your KYC is due for periodic update. Visit your nearest branch or use bob World app. Never share OTP."""),
    ("none", """Cousin: didi I got the job offer from Accenture!! joining in Nov
Me: congrats!!"""),
    ("none", """Group admin: Society meeting on Sunday 6pm about the water tank. Please attend."""),
    ("none", """Ravi: lost my wallet lol, can you pay the auto 150 and I'll return tonight
Me: done
Ravi: thanks, sent back"""),
    ("none", """Flipkart: Your refund of Rs 1,299 for order OD123 has been processed to your original payment method. It will reflect in 5-7 days."""),
]

HELDOUT_UPI = [
    ("danger", "Dear customer, a refund of Rs 3,200 is pending. Please approve the payment request on PhonePe to get the money."),
    ("danger", "Shopkeeper said scan this qr code, it will credit 500 rs cashback into ur account"),
    ("danger", "Arey bhai mistake se 1500 bhej diya, wapas kar do please, galti se hua"),
    ("danger", "Your CRED reward of Rs 2,000 is ready. Approve collect request from rewards.cred@axl to claim"),
    ("danger", "Pay Rs 1 to verify your account and receive Rs 5,000 loan instantly. UPI: quickloan.verify@ybl"),
    ("danger", "Army officer: I have sent request money 12000, just enter your pin to receive the payment for your scooty"),
    ("caution", "Ramesh Electricals has requested Rs 2,350. Note: AC repair"),
    ("caution", "upi://pay?pa=dominos.blr@hdfcbank&pn=Dominos%20Pizza&am=459&mc=5814"),
    ("info", "Acct XX889 credited with Rs.20000.00 on 11-Oct-26 by NEFT from MOTHER. Avl Bal Rs.43,210.50 -Canara Bank"),
    ("none", "Please bring the cash for the picnic tomorrow"),
    ("none", "Contact us at support@phonepe.com for any issues"),
    ("none", "Your Paytm OTP is 334455. Valid for 10 minutes. Do not share."),
]

HELDOUT_CALLS = [
    ("scam", "Ma'am you are speaking to cyber crime department, a complaint is against your number, you have to come to Delhi or join video call immediately"),
    ("scam", "Hello I am calling from HDFC credit card department, your card limit is upgraded, just tell the CVV on the back"),
    ("scam", "Dadi it's me, your grandson, I am in trouble with police, please send 50,000 right now and don't tell papa"),
    ("scam", "Sir there is a refund for your electricity bill, I am sending a collect request, approve the request to get the refund"),
    ("scam", "Download the TeamViewer Quick Support application so I can fix your net banking issue"),
    ("scam", "Your Aadhaar card has been misused, a case is filed. Do not cut the call or you will be arrested."),
    ("scam", "Hello, Amazon gift card dena padega fine bharne ke liye, warna arrest warrant nikal jayega"),
    ("safe", "Hi sir, calling from Airtel about your broadband installation, the technician will come at 4 pm."),
    ("safe", "Beta the plumber is coming tomorrow, will you be home?"),
    ("safe", "Hello this is the bank branch, your new cheque book is ready for pickup at the branch."),
    ("safe", "Ma'am your Zomato order will be late by ten minutes, sorry for the delay."),
    ("safe", "Hey, it's Arjun, I'm running late for the meeting, start without me."),
]

# Single messages for the main message analyzer in its offline (rule engine) mode. Held out.
# label: "scam" or "safe". Predicted scam when the risk score is 25 or more ("Suspicious" or higher).
HELDOUT_MESSAGES = [
    ("scam", "Dear SBI user, your YONO account is blocked due to PAN not updated. Click http://sbi-pan-update.top to activate within 2 hrs."),
    ("scam", "Congrats! You have won Rs 50,00,000 in WhatsApp lucky draw. Contact Mr. Shah on +44 7700 900123 to claim."),
    ("scam", "Your electricity will be disconnected tonight at 9:30 PM as your bill is not updated. Call officer 9876500000 immediately."),
    ("scam", "Work from home opportunity! Earn 5000 daily by rating products. Message on Telegram t.me/easyjob_hr"),
    ("scam", "Income Tax Dept: You are eligible for a refund of Rs 15,490. Submit your bank details at incometax-refund.in.net"),
    ("scam", "Your parcel could not be delivered due to an incomplete address. Update here within 24 hours: https://indiapost.parcel-help.com"),
    ("scam", "Hi mom, this is my new number, my phone broke. Can you send 20000 urgently? Don't call, I can't talk now."),
    ("scam", "Netflix: your payment failed and your membership will be cancelled. Update your card at netf1ix-billing.com"),
    ("scam", "You are selected for Amazon work from home job. Pay Rs 1,999 registration fee to activate your ID."),
    ("scam", "Dear customer, share the OTP sent to your mobile to stop the Rs 49,999 transaction on your card."),
    ("scam", "KYC of your Paytm account is pending. Download the app from paytm-kyc.apk link and enter your details now or account will be closed."),
    ("scam", "Guaranteed 10% weekly returns! Join our crypto VIP group, limited seats, invest today."),
    ("safe", "Your OTP for HDFC Bank net banking login is 728194. Do not share this OTP with anyone."),
    ("safe", "Hi team, the sprint review is moved to 3 pm tomorrow. Please update your tickets before that."),
    ("safe", "Your Amazon order #405-1234567 has been delivered. Rate your experience in the app."),
    ("safe", "Reminder: your electricity bill of Rs 1,240 is due on 20 Oct. Pay on the official app or website."),
    ("safe", "Hey! Are we still on for dinner on Saturday? Let me know."),
    ("safe", "Your appointment with Dr. Rao is confirmed for 14 Oct at 11:00 AM. Reply C to cancel."),
    ("safe", "Thank you for applying to the SDE internship. We will review your application and get back within two weeks."),
    ("safe", "Rs 500 credited to your account from Priya via UPI. Available balance Rs 3,420."),
    ("safe", "The library will remain closed on Monday for Diwali. Books due that day can be returned on Tuesday."),
    ("safe", "Your Swiggy order is out for delivery and will reach in 20 minutes."),
    ("safe", "Hi, I've shared the project report on Google Drive. Please add your section by Friday."),
    ("safe", "Jio: Your monthly plan of Rs 299 has been renewed successfully. Validity till 12 Nov."),
]
