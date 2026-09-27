"""Everything the citizen assistant can say, in English, Hindi, Marathi and
Hinglish (romanized Hindi, for people who type that way).

Fixed templates, never generated text: the only variable parts are values
read from the database, so a reply cannot contain an ID, date or score that
isn't on record. Wording follows the product rules: evidence, verification,
human review - never fraud, blame or guilt. The Hindi/Marathi phrasing
avoids first-person verbs, which are gendered in both languages.
"""

# key: (en, hi, mr, hinglish)
T: dict[str, tuple[str, str, str, str]] = {
    "menu": (
        "You can report a civic problem here, track a report you've sent, or check an existing issue. "
        "Describe the problem in your own words - English, हिंदी or मराठी.",
        "यहाँ आप नागरिक समस्या दर्ज कर सकते हैं, भेजी गई शिकायत की स्थिति देख सकते हैं, या किसी मौजूदा समस्या की "
        "जानकारी ले सकते हैं। समस्या अपने शब्दों में लिखिए।",
        "इथे तुम्ही नागरी समस्येची तक्रार करू शकता, पाठवलेल्या तक्रारीची स्थिती पाहू शकता किंवा आधी नोंदलेल्या "
        "समस्येची माहिती घेऊ शकता. समस्या तुमच्या शब्दांत लिहा.",
        "Yahan aap civic problem report kar sakte hain, apni bheji hui report track kar sakte hain, ya kisi "
        "existing issue ki jaankari le sakte hain. Problem apne shabdon mein likhiye.",
    ),
    "understood": (
        "I understand this as a {category} issue{where}. Do you want to report it here?",
        "इसे {category} की समस्या समझा गया है{where}। क्या आप इसे यहाँ दर्ज करना चाहते हैं?",
        "ही {category} संबंधित समस्या असल्याचे समजले{where}. ही तक्रार इथे नोंदवायची आहे का?",
        "Ise {category} ki problem samjha gaya hai{where}. Kya aap ise yahan report karna chahenge?",
    ),
    "where": (" near {clue}", " ({clue} के पास)", " ({clue} जवळ)", " ({clue} ke paas)"),
    "ask_category": (
        "Which kind of problem is it closest to?",
        "यह किस तरह की समस्या के सबसे करीब है?",
        "ही समस्या कोणत्या प्रकारात मोडते?",
        "Yeh kis type ki problem ke sabse kareeb hai?",
    ),
    "ask_describe": (
        "Please describe the problem in a sentence or two: what it is and roughly where.",
        "कृपया समस्या एक-दो वाक्यों में बताइए: क्या है और लगभग कहाँ है।",
        "कृपया समस्या एक-दोन वाक्यांत सांगा: काय आहे आणि साधारण कुठे आहे.",
        "Please problem ek-do line mein bataiye: kya hai aur lagbhag kahan hai.",
    ),
    "similar_intro": (
        "Describe the problem and share where it is. CivicFix will look for an existing Civic Issue first - "
        "nothing is sent until you confirm.",
        "समस्या और जगह बताइए। CivicFix पहले मौजूदा Civic Issue खोजेगा - आपकी पुष्टि के बिना कुछ नहीं भेजा जाएगा।",
        "समस्या आणि ठिकाण सांगा. CivicFix आधी नोंदलेला Civic Issue शोधेल - तुमच्या पुष्टीशिवाय काहीही पाठवले जाणार नाही.",
        "Problem aur jagah bataiye. CivicFix pehle existing Civic Issue dhoondhega - aapke confirm kiye bina "
        "kuch nahi bheja jayega.",
    ),
    "ask_issue_number": (
        "Type the issue number, for example #PMC-12, or describe the problem and where it is.",
        "मुद्दे का नंबर लिखिए, जैसे #PMC-12, या समस्या और जगह बताइए।",
        "मुद्द्याचा क्रमांक लिहा, उदा. #PMC-12, किंवा समस्या आणि ठिकाण सांगा.",
        "Issue number likhiye, jaise #PMC-12, ya problem aur jagah bataiye.",
    ),
    "ask_location": (
        "Please share your location or drop a pin, so CivicFix can check whether this matches an existing "
        "Civic Issue. You can also type a nearby street or landmark.",
        "कृपया अपनी लोकेशन साझा करें या नक्शे पर पिन लगाएँ, ताकि देखा जा सके कि यह किसी मौजूदा Civic Issue से "
        "मेल खाती है या नहीं। आप पास की सड़क या कोई पहचान चिह्न भी लिख सकते हैं।",
        "कृपया तुमचे लोकेशन शेअर करा किंवा नकाशावर पिन लावा, म्हणजे ही समस्या आधी नोंदलेल्या Civic Issue शी "
        "जुळते का ते पाहता येईल. जवळचा रस्ता किंवा खूण लिहिली तरी चालेल.",
        "Please apni location share kijiye ya map par pin lagaiye, taaki check ho sake ki yeh kisi existing "
        "Civic Issue se match karta hai ya nahi. Aap paas ki sadak ya landmark bhi likh sakte hain.",
    ),
    "ask_landmark": (
        "Type the street name or a nearby landmark.",
        "सड़क का नाम या पास का कोई पहचान चिह्न लिखिए।",
        "रस्त्याचे नाव किंवा जवळची खूण लिहा.",
        "Sadak ka naam ya paas ka koi landmark likhiye.",
    ),
    "location_ok": (
        "Location received: {ward}.",
        "लोकेशन मिल गई: {ward}।",
        "लोकेशन मिळाले: {ward}.",
        "Location mil gayi: {ward}.",
    ),
    "location_fail": (
        "I couldn't confidently identify the exact location. Please drop a pin or give a nearby landmark - "
        "or send it with the locality information you gave.",
        "सटीक जगह पक्की नहीं हो सकी। कृपया पिन लगाएँ या पास का कोई पहचान चिह्न बताइए - या दी गई जानकारी के साथ "
        "ही भेज दें।",
        "नेमके ठिकाण निश्चित करता आले नाही. कृपया पिन लावा किंवा जवळची खूण सांगा - किंवा दिलेल्या माहितीसह "
        "तक्रार पाठवा.",
        "Exact location confirm nahi ho saki. Please pin lagaiye ya paas ka koi landmark bataiye - ya di hui "
        "jaankari ke saath hi bhej dijiye.",
    ),
    "location_outside": (
        "That point is outside the Pune wards CivicFix covers. Please drop a pin inside Pune or type a landmark.",
        "यह जगह CivicFix के पुणे वार्डों से बाहर है। कृपया पुणे के अंदर पिन लगाएँ या पहचान चिह्न लिखें।",
        "हे ठिकाण CivicFix च्या पुणे प्रभागांबाहेर आहे. कृपया पुण्यातच पिन लावा किंवा खूण लिहा.",
        "Yeh point CivicFix ke Pune wards ke bahar hai. Please Pune ke andar pin lagaiye ya landmark likhiye.",
    ),
    "location_skipped": (
        "Okay. It will be sent with the locality in your description; if that isn't enough, a ward officer "
        "will place it. No location will be guessed.",
        "ठीक है। इसे आपके विवरण में दी गई जगह के साथ भेजा जाएगा; वह काफ़ी न हो तो वार्ड अधिकारी जगह तय करेंगे। "
        "कोई जगह अनुमान से नहीं भरी जाएगी।",
        "ठीक आहे. तुमच्या वर्णनातील ठिकाणासह तक्रार पाठवली जाईल; ते पुरेसे नसल्यास प्रभाग अधिकारी जागा निश्चित "
        "करतील. कोणतेही ठिकाण अंदाजाने भरले जाणार नाही.",
        "Theek hai. Ise aapke description mein di gayi jagah ke saath bheja jayega; woh kaafi na ho to ward "
        "officer jagah tay karenge. Koi location andaaze se nahi bhari jayegi.",
    ),
    "ask_photo": (
        "Would you like to add a photo? It's kept as evidence for the ward officer; it doesn't decide how "
        "serious the issue is.",
        "क्या आप फ़ोटो जोड़ना चाहेंगे? यह वार्ड अधिकारी के लिए सबूत के तौर पर रखी जाती है; इससे समस्या की गंभीरता "
        "तय नहीं होती।",
        "फोटो जोडायचा आहे का? तो प्रभाग अधिकाऱ्यांसाठी पुरावा म्हणून ठेवला जातो; त्यावरून समस्येची गंभीरता ठरत नाही.",
        "Kya aap photo add karna chahenge? Yeh ward officer ke liye evidence ke roop mein rakhi jaati hai; isse "
        "problem ki seriousness tay nahi hoti.",
    ),
    "photo_ok": ("Photo attached.", "फ़ोटो जुड़ गई।", "फोटो जोडला.", "Photo add ho gayi."),
    "match_many": (
        "I found {n} reports near this location that appear to describe the same problem. Your report can be "
        "added to this Civic Issue instead of creating a duplicate.",
        "इस जगह के पास {n} शिकायतें मिलीं जो इसी समस्या के बारे में लगती हैं। नई डुप्लिकेट शिकायत बनाने के बजाय "
        "आपकी शिकायत इसी Civic Issue में जोड़ी जा सकती है।",
        "या ठिकाणाजवळ {n} तक्रारी सापडल्या ज्या याच समस्येबद्दल वाटतात. नवीन दुहेरी तक्रार करण्याऐवजी तुमची "
        "तक्रार याच Civic Issue मध्ये जोडता येईल.",
        "Is location ke paas {n} reports mile jo isi problem ke baare mein lagte hain. Nayi duplicate complaint "
        "banane ki jagah aapki report isi Civic Issue mein jodi ja sakti hai.",
    ),
    "match_one": (
        "I found an earlier report near this location that appears to describe the same problem. Your report "
        "can be added to it, as one Civic Issue.",
        "इस जगह के पास एक पुरानी शिकायत मिली जो इसी समस्या के बारे में लगती है। आपकी शिकायत उसके साथ एक Civic "
        "Issue के रूप में जोड़ी जा सकती है।",
        "या ठिकाणाजवळ याच समस्येबद्दलची एक आधीची तक्रार सापडली. तुमची तक्रार तिच्यासोबत एकाच Civic Issue मध्ये "
        "जोडता येईल.",
        "Is location ke paas ek pehle ki report mili jo isi problem ke baare mein lagti hai. Aapki report uske "
        "saath ek Civic Issue mein jodi ja sakti hai.",
    ),
    "recurrence": (
        "This appears to match {code}, which was marked resolved on {date}. If you send this report, it will be "
        "added as recurrence evidence and the issue will be reopened for verification.",
        "यह {code} से मेल खाती लगती है, जिसे {date} को हल बताया गया था। यह शिकायत भेजने पर इसे दोबारा होने के "
        "सबूत के रूप में जोड़ा जाएगा और मुद्दा सत्यापन के लिए फिर से खोला जाएगा।",
        "ही तक्रार {code} शी जुळते असे दिसते, जो {date} रोजी सोडवल्याचे नोंदले होते. ही तक्रार पाठवल्यास ती "
        "पुनरावृत्तीचा पुरावा म्हणून जोडली जाईल आणि पडताळणीसाठी मुद्दा पुन्हा उघडला जाईल.",
        "Yeh {code} se match karta lagta hai, jise {date} ko resolved mark kiya gaya tha. Yeh report bhejne par "
        "ise dobara hone ke evidence ke roop mein joda jayega aur issue verification ke liye reopen hoga.",
    ),
    "no_match": (
        "I couldn't find a reliable match nearby, so this will start a new Civic Issue.",
        "पास में कोई भरोसेमंद मेल नहीं मिला, इसलिए यह एक नया Civic Issue बनेगा।",
        "जवळपास खात्रीशीर जुळणारी तक्रार सापडली नाही, त्यामुळे हा नवीन Civic Issue असेल.",
        "Paas mein koi reliable match nahi mila, isliye yeh ek naya Civic Issue banega.",
    ),
    "preview_failed": (
        "I couldn't check for similar reports right now. You can still send it; it will be matched on arrival.",
        "अभी मिलती-जुलती शिकायतें जाँची नहीं जा सकीं। आप इसे फिर भी भेज सकते हैं; पहुँचने पर इसका मिलान होगा।",
        "सध्या सारख्या तक्रारी तपासता आल्या नाहीत. तरीही तुम्ही ती पाठवू शकता; पोहोचल्यावर जुळवणी होईल.",
        "Abhi similar reports check nahi ho sake. Aap ise phir bhi bhej sakte hain; pahunchne par match hoga.",
    ),
    "sent_joined": (
        "Your report has been added to Civic Issue {code}. It is being tracked together with {others} related "
        "report(s) - one problem, not separate tickets.",
        "आपकी शिकायत Civic Issue {code} में जोड़ दी गई है। इसे {others} संबंधित शिकायतों के साथ एक ही समस्या के "
        "रूप में ट्रैक किया जा रहा है।",
        "तुमची तक्रार Civic Issue {code} मध्ये जोडली आहे. ती इतर {others} संबंधित तक्रारींसोबत एकच समस्या म्हणून "
        "पाहिली जात आहे.",
        "Aapki report Civic Issue {code} mein jod di gayi hai. Ise {others} related reports ke saath ek hi "
        "problem ke roop mein track kiya ja raha hai.",
    ),
    "sent_new": (
        "Your report has started Civic Issue {code}. If others report the same problem, their reports will be "
        "grouped with yours.",
        "आपकी शिकायत से Civic Issue {code} शुरू हुआ है। दूसरे लोग यही समस्या बताएँगे तो उनकी शिकायतें इसी में "
        "जुड़ेंगी।",
        "तुमच्या तक्रारीतून Civic Issue {code} सुरू झाला आहे. इतरांनी हीच समस्या नोंदवल्यास त्यांच्या तक्रारी यातच "
        "जोडल्या जातील.",
        "Aapki report se Civic Issue {code} shuru hua hai. Doosre log yahi problem report karenge to unki "
        "reports isi mein judengi.",
    ),
    "sent_reopened": (
        "Your report was added to {code}, which had been marked resolved. It has been reopened for verification.",
        "आपकी शिकायत {code} में जोड़ी गई, जिसे हल बताया गया था। इसे सत्यापन के लिए फिर से खोला गया है।",
        "तुमची तक्रार {code} मध्ये जोडली, जो सोडवल्याचे नोंदले होते. पडताळणीसाठी तो पुन्हा उघडला आहे.",
        "Aapki report {code} mein jodi gayi, jise resolved mark kiya gaya tha. Ise verification ke liye reopen "
        "kiya gaya hai.",
    ),
    "sent_held": (
        "Your report has been received. A ward officer will read it before it appears on the public board.",
        "आपकी शिकायत मिल गई है। सार्वजनिक बोर्ड पर आने से पहले वार्ड अधिकारी इसे पढ़ेंगे।",
        "तुमची तक्रार मिळाली आहे. सार्वजनिक फलकावर येण्यापूर्वी प्रभाग अधिकारी ती वाचतील.",
        "Aapki report mil gayi hai. Public board par aane se pehle ward officer ise padhenge.",
    ),
    "sign_in": (
        "Please sign in so the report is linked to you and you get updates. Your draft is kept.",
        "कृपया साइन इन करें, ताकि शिकायत आपके खाते से जुड़े और आपको अपडेट मिलें। आपका ड्राफ्ट सुरक्षित है।",
        "कृपया साइन इन करा, म्हणजे तक्रार तुमच्या खात्याशी जोडली जाईल आणि तुम्हाला अपडेट मिळतील. तुमचा मसुदा "
        "जपून ठेवला आहे.",
        "Please sign in kijiye, taaki report aapke account se jude aur aapko updates milein. Aapka draft safe hai.",
    ),
    "track_none": (
        "You haven't sent any reports from this account yet.",
        "इस खाते से अभी तक कोई शिकायत नहीं भेजी गई है।",
        "या खात्यातून अजून एकही तक्रार पाठवलेली नाही.",
        "Is account se abhi tak koi report nahi bheji gayi hai.",
    ),
    "track_list": ("Your most recent reports:", "आपकी हाल की शिकायतें:", "तुमच्या अलीकडच्या तक्रारी:",
                   "Aapki haal ki reports:"),
    "issue_not_found": (
        "I don't have verified information about {code}. Please check the number.",
        "{code} के बारे में सत्यापित जानकारी उपलब्ध नहीं है। कृपया नंबर जाँच लें।",
        "{code} बद्दल पडताळलेली माहिती उपलब्ध नाही. कृपया क्रमांक तपासा.",
        "{code} ke baare mein verified jaankari uplabdh nahi hai. Please number check kijiye.",
    ),
    "issue_record": ("The current record for {code}:", "{code} का मौजूदा रिकॉर्ड:", "{code} ची सद्य नोंद:",
                     "{code} ka current record:"),
    "priority_intro": (
        "This issue is currently {level} priority because of:",
        "यह मुद्दा अभी {level} प्राथमिकता पर है, इन कारणों से:",
        "हा मुद्दा सध्या {level} प्राधान्यावर आहे, या कारणांमुळे:",
        "Yeh issue abhi {level} priority par hai, in wajahon se:",
    ),
    "priority_formula": (
        "The priority comes from a published formula, not an AI judgement, and its reasons are shown here.",
        "प्राथमिकता एक प्रकाशित सूत्र से तय होती है, AI के फ़ैसले से नहीं, और इसके कारण यहाँ दिखाए गए हैं।",
        "प्राधान्य एका जाहीर सूत्रावरून ठरते, AI च्या निर्णयावरून नाही, आणि त्याची कारणे इथे दाखवली आहेत.",
        "Priority ek published formula se tay hoti hai, AI ke faisle se nahi, aur iski wajahein yahan hain.",
    ),
    "priority_none": (
        "No priority has been computed for this issue yet.",
        "इस मुद्दे की प्राथमिकता अभी तय नहीं हुई है।",
        "या मुद्द्याचे प्राधान्य अजून ठरलेले नाही.",
        "Is issue ki priority abhi compute nahi hui hai.",
    ),
    "priority_private": (
        "Priority details are shared with the people who reported this issue.",
        "प्राथमिकता का विवरण इस समस्या की शिकायत करने वालों को दिखाया जाता है।",
        "प्राधान्याचा तपशील ही समस्या नोंदवणाऱ्यांना दाखवला जातो.",
        "Priority ki details is issue ko report karne walon ko dikhayi jaati hain.",
    ),
    "f_severity": ("how serious the reported problem is ({band})", "बताई गई समस्या की गंभीरता ({band})",
                   "नोंदलेल्या समस्येची गंभीरता ({band})", "report ki gayi problem kitni serious hai ({band})"),
    "f_exposure": ("public exposure: a {site} nearby", "सार्वजनिक असर: पास में {site}", "सार्वजनिक परिणाम: जवळ {site}",
                   "public exposure: paas mein {site}"),
    "f_recurrence": ("it has come back {n} time(s) after being resolved", "हल होने के बाद यह {n} बार लौटी है",
                     "सोडवल्यानंतर ही {n} वेळा परत आली आहे", "resolve hone ke baad yeh {n} baar wapas aayi hai"),
    "f_time": ("it has been open for {d} days", "यह {d} दिनों से खुली है", "ही {d} दिवसांपासून प्रलंबित आहे",
               "yeh {d} din se open hai"),
    "work_found": (
        "A related public work is recorded near this location. CivicFix does not assume that it resolved the "
        "reported problem.",
        "इस जगह के पास एक संबंधित सार्वजनिक कार्य दर्ज है। CivicFix यह नहीं मानता कि उससे बताई गई समस्या हल हो गई।",
        "या ठिकाणाजवळ एक संबंधित सार्वजनिक काम नोंदलेले आहे. त्या कामामुळे नोंदलेली समस्या सुटली असे CivicFix "
        "गृहीत धरत नाही.",
        "Is location ke paas ek related public work recorded hai. CivicFix yeh maan kar nahi chalta ki usse "
        "report ki gayi problem solve ho gayi.",
    ),
    "work_after": (
        "The work is recorded as completed on {date}. {n} similar report(s) were received afterwards.",
        "यह कार्य {date} को पूरा दर्ज है। उसके बाद {n} मिलती-जुलती शिकायतें आईं।",
        "हे काम {date} रोजी पूर्ण झाल्याचे नोंदले आहे. त्यानंतर {n} सारख्या तक्रारी आल्या.",
        "Yeh kaam {date} ko complete recorded hai. Uske baad {n} similar reports aaye.",
    ),
    "work_flagged": (
        "CivicFix has flagged this for human verification.",
        "CivicFix ने इसे मानवीय सत्यापन के लिए चिह्नित किया है।",
        "CivicFix ने हे मानवी पडताळणीसाठी चिन्हांकित केले आहे.",
        "CivicFix ne ise human verification ke liye flag kiya hai.",
    ),
    "work_none": (
        "I don't have a verified record of public work linked to this issue.",
        "इस मुद्दे से जुड़े किसी सार्वजनिक कार्य का सत्यापित रिकॉर्ड उपलब्ध नहीं है।",
        "या मुद्द्याशी जोडलेल्या सार्वजनिक कामाची पडताळलेली नोंद उपलब्ध नाही.",
        "Is issue se jude kisi public work ka verified record uplabdh nahi hai.",
    ),
    "history_found": (
        "Within {r} m of this issue there are {k} earlier {category} issue(s): {closed} marked resolved, "
        "{reopened} reopened after a resolution.",
        "इस मुद्दे के {r} मीटर के भीतर {category} के {k} पुराने मुद्दे हैं: {closed} हल बताए गए, {reopened} हल होने "
        "के बाद फिर खुले।",
        "या मुद्द्याच्या {r} मीटरच्या आत {category} चे {k} आधीचे मुद्दे आहेत: {closed} सोडवल्याचे नोंदले, "
        "{reopened} सोडवल्यानंतर पुन्हा उघडले.",
        "Is issue ke {r} m ke andar {category} ke {k} purane issues hain: {closed} resolved mark hue, {reopened} "
        "resolve hone ke baad phir khule.",
    ),
    "history_self": (
        "This issue itself has come back {n} time(s) after being marked resolved.",
        "यह मुद्दा खुद हल बताए जाने के बाद {n} बार लौटा है।",
        "हा मुद्दा स्वतः सोडवल्याचे नोंदल्यानंतर {n} वेळा परत आला आहे.",
        "Yeh issue khud resolved mark hone ke baad {n} baar wapas aaya hai.",
    ),
    "history_none": (
        "I don't have a record of earlier {category} issues within {r} m of this location.",
        "इस जगह के {r} मीटर के भीतर {category} के पुराने मुद्दों का कोई रिकॉर्ड नहीं है।",
        "या ठिकाणाच्या {r} मीटरच्या आत {category} च्या आधीच्या मुद्द्यांची नोंद नाही.",
        "Is location ke {r} m ke andar {category} ke purane issues ka koi record nahi hai.",
    ),
    "history_no_location": (
        "This issue has no mapped location, so it can't be compared with nearby history.",
        "इस मुद्दे की जगह नक्शे पर दर्ज नहीं है, इसलिए आसपास के इतिहास से तुलना नहीं हो सकती।",
        "या मुद्द्याचे ठिकाण नकाशावर नोंदलेले नाही, त्यामुळे आसपासच्या इतिहासाशी तुलना करता येत नाही.",
        "Is issue ki location map par nahi hai, isliye aas-paas ki history se compare nahi ho sakta.",
    ),
    "confirm_closed": (
        "The officer marked {code} resolved on {date}. Resolved is a status; verified is evidence. Is the "
        "problem actually fixed?",
        "अधिकारी ने {code} को {date} को हल बताया। 'हल' एक स्थिति है, 'सत्यापित' सबूत है। क्या समस्या सच में ठीक "
        "हो गई है?",
        "अधिकाऱ्यांनी {code} {date} रोजी सोडवल्याचे नोंदले. 'सोडवले' ही स्थिती आहे; 'पडताळले' हा पुरावा आहे. समस्या "
        "खरोखर दूर झाली आहे का?",
        "Officer ne {code} ko {date} ko resolved mark kiya. Resolved ek status hai; verified evidence hai. Kya "
        "problem sach mein theek ho gayi hai?",
    ),
    "confirm_dispatch": (
        "Before a crew is sent for {code}, can you confirm whether the problem is still there?",
        "{code} के लिए टीम भेजने से पहले, क्या आप बता सकते हैं कि समस्या अब भी है?",
        "{code} साठी पथक पाठवण्यापूर्वी, समस्या अजूनही आहे का ते सांगू शकाल का?",
        "{code} ke liye team bhejne se pehle, kya aap bata sakte hain ki problem abhi bhi hai?",
    ),
    "thanks_confirmed": (
        "Thank you. Your confirmation is recorded as evidence.",
        "धन्यवाद। आपकी पुष्टि सबूत के रूप में दर्ज हो गई है।",
        "धन्यवाद. तुमची पुष्टी पुरावा म्हणून नोंदली आहे.",
        "Dhanyavaad. Aapka confirmation evidence ke roop mein record ho gaya hai.",
    ),
    "thanks_disputed": (
        "Thank you. The issue has been reopened for verification, and your answer is recorded as evidence.",
        "धन्यवाद। मुद्दे को सत्यापन के लिए फिर से खोला गया है और आपका जवाब सबूत के रूप में दर्ज है।",
        "धन्यवाद. मुद्दा पडताळणीसाठी पुन्हा उघडला आहे आणि तुमचे उत्तर पुरावा म्हणून नोंदले आहे.",
        "Dhanyavaad. Issue verification ke liye reopen ho gaya hai aur aapka jawab evidence ke roop mein record hai.",
    ),
    "thanks_recorded": (
        "Thank you, your answer is recorded for the ward team.",
        "धन्यवाद, आपका जवाब वार्ड टीम के लिए दर्ज कर लिया गया है।",
        "धन्यवाद, तुमचे उत्तर प्रभाग टीमसाठी नोंदले आहे.",
        "Dhanyavaad, aapka jawab ward team ke liye record ho gaya hai.",
    ),
    "not_sure": ("No problem. Nothing has been changed.", "कोई बात नहीं। कुछ नहीं बदला गया।",
                 "हरकत नाही. काहीही बदललेले नाही.", "Koi baat nahi. Kuch bhi badla nahi gaya."),
    "cancelled": ("Okay, the draft has been discarded.", "ठीक है, ड्राफ्ट हटा दिया गया।", "ठीक आहे, मसुदा रद्द केला.",
                  "Theek hai, draft hata diya gaya."),
    "lang_set": ("I'll reply in English.", "अब से हिंदी में जवाब दिया जाएगा।", "आता मराठीत उत्तर दिले जाईल.",
                 "Ab se Hinglish mein jawab diya jayega."),
    "service_error": (
        "The CivicFix service couldn't complete that ({detail}). Your draft is still here; please try again.",
        "CivicFix सेवा यह पूरा नहीं कर सकी ({detail})। आपका ड्राफ्ट सुरक्षित है; कृपया फिर कोशिश करें।",
        "CivicFix सेवा हे पूर्ण करू शकली नाही ({detail}). तुमचा मसुदा जपून ठेवला आहे; कृपया पुन्हा प्रयत्न करा.",
        "CivicFix service yeh poora nahi kar saki ({detail}). Aapka draft safe hai; please phir try kijiye.",
    ),
    # Status labels - "resolved" is a status, "verified" needs evidence.
    "st_reported": ("Reported", "दर्ज", "नोंदवले", "Reported"),
    "st_routed": ("Routed to {agency}", "{agency} को भेजा गया", "{agency} कडे पाठवले", "{agency} ko bheja gaya"),
    "st_assigned": ("Field team assigned", "फ़ील्ड टीम नियुक्त", "फील्ड पथक नेमले", "Field team assign hui"),
    "st_resolved_window": (
        "Marked resolved - awaiting citizen verification until {date}",
        "हल बताया गया - {date} तक नागरिक सत्यापन की प्रतीक्षा",
        "सोडवल्याचे नोंदले - {date} पर्यंत नागरिक पडताळणीची प्रतीक्षा",
        "Resolved mark hua - {date} tak citizen verification ka intezaar",
    ),
    "st_verified": ("Marked resolved - confirmed by a reporter", "हल बताया गया - शिकायतकर्ता ने पुष्टि की",
                    "सोडवल्याचे नोंदले - तक्रारदाराने पुष्टी केली", "Resolved mark hua - reporter ne confirm kiya"),
    "st_resolved": ("Marked resolved", "हल बताया गया", "सोडवल्याचे नोंदले", "Resolved mark hua"),
    "st_reopened": ("Reopened for verification", "सत्यापन के लिए फिर से खोला गया", "पडताळणीसाठी पुन्हा उघडले",
                    "Verification ke liye reopen hua"),
    "st_under_review": ("Under review by a ward officer", "वार्ड अधिकारी की समीक्षा में", "प्रभाग अधिकाऱ्यांच्या तपासणीत",
                        "Ward officer ke review mein"),
    # Buttons
    "b_report_it": ("Report it", "शिकायत दर्ज करें", "तक्रार नोंदवा", "Report karein"),
    "b_not_now": ("Not now", "अभी नहीं", "आत्ता नाही", "Abhi nahi"),
    "b_change_category": ("Change category", "श्रेणी बदलें", "प्रकार बदला", "Category badlein"),
    "b_use_location": ("Use my location", "मेरी लोकेशन", "माझे लोकेशन", "Meri location"),
    "b_drop_pin": ("Drop a pin", "पिन लगाएँ", "पिन लावा", "Pin lagayein"),
    "b_type_landmark": ("Type a landmark", "पहचान चिह्न लिखें", "खूण लिहा", "Landmark likhein"),
    "b_skip": ("Skip", "छोड़ें", "वगळा", "Skip"),
    "b_send_without": ("Send with locality info", "दी गई जानकारी से भेजें", "दिलेल्या माहितीसह पाठवा",
                       "Di hui jaankari se bhejein"),
    "b_add_photo": ("Add photo", "फ़ोटो जोड़ें", "फोटो जोडा", "Photo add karein"),
    "b_send": ("Send report", "शिकायत भेजें", "तक्रार पाठवा", "Report bhejein"),
    "b_add_to_issue": ("Add to this issue", "इसी मुद्दे में जोड़ें", "याच मुद्द्यात जोडा", "Isi issue mein jodein"),
    "b_report_separately": ("Report separately", "अलग से दर्ज करें", "स्वतंत्र नोंदवा", "Alag se report karein"),
    "b_cancel": ("Cancel", "रद्द करें", "रद्द करा", "Cancel"),
    "b_fixed": ("Fixed", "ठीक हो गई", "दुरुस्त झाली", "Theek ho gayi"),
    "b_still_there": ("Still there", "अब भी है", "अजून आहे", "Abhi bhi hai"),
    "b_not_sure": ("Not sure", "पता नहीं", "माहीत नाही", "Pata nahi"),
    "b_view_issue": ("View issue page", "मुद्दा देखें", "मुद्दा पाहा", "Issue dekhein"),
    "b_why_priority": ("Why this priority?", "यह प्राथमिकता क्यों?", "हे प्राधान्य का?", "Yeh priority kyun?"),
    "b_related_work": ("Was anything done here?", "क्या यहाँ कोई काम हुआ?", "इथे काही काम झाले का?",
                       "Yahan kuch kaam hua?"),
    "b_history": ("Has this happened before?", "क्या पहले भी हुआ?", "आधीही झाले होते का?", "Pehle bhi hua?"),
    "b_track": ("Track my issue", "मेरी शिकायतें", "माझ्या तक्रारी", "Meri reports"),
    "b_report": ("Report an issue", "समस्या दर्ज करें", "समस्या नोंदवा", "Problem report karein"),
    "b_similar": ("Find a similar issue", "मिलती-जुलती समस्या खोजें", "सारखी समस्या शोधा", "Similar issue dhoondhein"),
    "b_check": ("Check an existing problem", "मौजूदा समस्या देखें", "नोंदलेली समस्या पाहा", "Existing problem dekhein"),
    "b_sign_in": ("Sign in", "साइन इन", "साइन इन", "Sign in"),
    # Card labels
    "l_status": ("Status", "स्थिति", "स्थिती", "Status"),
    "l_reports": ("Reports", "शिकायतें", "तक्रारी", "Reports"),
    "l_ward": ("Ward", "वार्ड", "प्रभाग", "Ward"),
    "l_first": ("First reported", "पहली शिकायत", "पहिली तक्रार", "Pehli report"),
    "l_last": ("Latest report", "आख़िरी शिकायत", "शेवटची तक्रार", "Latest report"),
    "l_category": ("Category", "श्रेणी", "प्रकार", "Category"),
    "l_location": ("Location", "जगह", "ठिकाण", "Location"),
    "l_since": ("Since (your words)", "कब से (आपके शब्द)", "केव्हापासून (तुमचे शब्द)", "Kab se (aapke shabd)"),
    "l_photo": ("Photo", "फ़ोटो", "फोटो", "Photo"),
    "l_text": ("Will be sent as", "ऐसे भेजा जाएगा", "असे पाठवले जाईल", "Aise bheja jayega"),
    "l_agency": ("Agency", "एजेंसी", "यंत्रणा", "Agency"),
    "l_recorded_status": ("Recorded status", "दर्ज स्थिति", "नोंदलेली स्थिती", "Recorded status"),
    "l_completed": ("Recorded completion", "दर्ज पूर्णता तिथि", "नोंदलेली पूर्णता तारीख", "Recorded completion"),
    "l_cost": ("Sanctioned cost", "स्वीकृत लागत", "मंजूर खर्च", "Sanctioned cost"),
    "l_distance": ("Distance from issue", "मुद्दे से दूरी", "मुद्द्यापासून अंतर", "Issue se doori"),
    "l_why_linked": ("Why it is linked", "क्यों जोड़ा गया", "का जोडले", "Kyun joda gaya"),
    "l_source": ("Source", "स्रोत", "स्रोत", "Source"),
    "l_after": ("Reports after completion", "पूर्णता के बाद शिकायतें", "पूर्णतेनंतरच्या तक्रारी",
                "Completion ke baad reports"),
    "l_verification": ("Verification", "सत्यापन", "पडताळणी", "Verification"),
    "v_flagged": ("Flagged for human verification", "मानवीय सत्यापन के लिए चिह्नित", "मानवी पडताळणीसाठी चिन्हांकित",
                  "Human verification ke liye flagged"),
    "v_not_flagged": ("No verification signal", "कोई सत्यापन संकेत नहीं", "पडताळणी संकेत नाही",
                      "Koi verification signal nahi"),
    "v_attached": ("Attached (kept as evidence)", "जुड़ी है (सबूत के रूप में)", "जोडला (पुरावा म्हणून)",
                   "Attached (evidence ke roop mein)"),
    "v_pin": ("Your pin / GPS point", "आपकी पिन / GPS", "तुमची पिन / GPS", "Aapki pin / GPS"),
    "v_not_given": ("Not given", "नहीं दी गई", "दिलेले नाही", "Nahi di gayi"),
    "v_ward_level": ("ward level, approximate", "वार्ड स्तर, अनुमानित", "प्रभाग स्तर, अंदाजे", "ward level, approximate"),
    "t_summary": ("Your report", "आपकी शिकायत", "तुमची तक्रार", "Aapki report"),
    "t_work": ("Related public work", "संबंधित सार्वजनिक कार्य", "संबंधित सार्वजनिक काम", "Related public work"),
    "t_priority": ("Priority", "प्राथमिकता", "प्राधान्य", "Priority"),
    "t_outcome": ("Work → outcome", "कार्य → परिणाम", "काम → परिणाम", "Work → outcome"),
    "t_history": ("Civic memory", "नागरिक स्मृति", "नागरी स्मृती", "Civic memory"),
    "t_reports": ("Your reports", "आपकी शिकायतें", "तुमच्या तक्रारी", "Aapki reports"),
    "s_first": ("Issue first reported", "मुद्दा पहली बार दर्ज", "मुद्दा प्रथम नोंदला", "Issue pehli baar report hua"),
    "s_work": ("Related work", "संबंधित कार्य", "संबंधित काम", "Related work"),
    # Levels, bands, sites
    "lv_high": ("High", "उच्च", "उच्च", "High"),
    "lv_med": ("Medium", "मध्यम", "मध्यम", "Medium"),
    "lv_low": ("Low", "निम्न", "कमी", "Low"),
    "band_critical": ("serious", "गंभीर", "गंभीर", "serious"),
    "band_moderate": ("moderate", "मध्यम", "मध्यम", "moderate"),
    "band_cosmetic": ("minor", "मामूली", "किरकोळ", "minor"),
    "site_school": ("school", "स्कूल", "शाळा", "school"),
    "site_hospital": ("hospital", "अस्पताल", "रुग्णालय", "hospital"),
    "site_market": ("market", "बाज़ार", "बाजार", "market"),
    "site_water_body": ("water body", "जलाशय", "जलाशय", "water body"),
    "site_bus_stop": ("bus stop", "बस स्टॉप", "बस थांबा", "bus stop"),
    "site_college": ("college", "कॉलेज", "महाविद्यालय", "college"),
    "site_clinic": ("clinic", "क्लिनिक", "दवाखाना", "clinic"),
    "site_heritage": ("heritage site", "धरोहर स्थल", "वारसा स्थळ", "heritage site"),
    # Categories
    "cat_pothole_road": ("Road / pothole", "सड़क / गड्ढा", "रस्ता / खड्डा", "Sadak / gaddha"),
    "cat_drainage_sewage": ("Drainage / waterlogging", "नाली / जलभराव", "गटार / पाणी साचणे", "Drainage / paani jama"),
    "cat_water_supply": ("Water supply", "पानी की आपूर्ति", "पाणीपुरवठा", "Paani supply"),
    "cat_streetlight": ("Streetlight", "स्ट्रीटलाइट", "पथदिवा", "Streetlight"),
    "cat_garbage_waste": ("Garbage / waste", "कचरा", "कचरा", "Kachra"),
    "cat_footpath": ("Footpath", "फुटपाथ", "पदपथ", "Footpath"),
    "cat_traffic_signage": ("Traffic signal / signage", "ट्रैफ़िक संकेत", "वाहतूक चिन्हे", "Traffic signal / sign"),
    "cat_other": ("Other civic", "अन्य", "इतर", "Other"),
}

_INDEX = {"en": 0, "hi": 1, "mr": 2, "hinglish": 3}


def t(key: str, lang: str = "en", **values) -> str:
    """The template in `lang`, falling back to English; values filled in."""
    text = T[key][_INDEX.get(lang, 0)]
    return text.format(**values) if values else text


def category_label(category: str | None, lang: str) -> str:
    return t(f"cat_{category}", lang) if f"cat_{category}" in T else t("cat_other", lang)


def site_label(kind: str, lang: str) -> str:
    return t(f"site_{kind}", lang) if f"site_{kind}" in T else kind.replace("_", " ")
