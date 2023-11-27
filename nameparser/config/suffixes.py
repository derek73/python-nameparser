# -*- coding: utf-8 -*-
from __future__ import unicode_literals

SUFFIX_NOT_ACRONYMS = set([
    'dr',
    'esq',
    'esquire',
    'jr',
    'jnr',
    'junior',
    'sr',
    'snr',
    '2',
    'i',
    'ii',
    'iii',
    'iv',
    'v',
])
"""

Post-nominal pieces that are not acronyms. The parser does not remove periods
when matching against these pieces.

"""
# WARNING: comments explaining the meaning of the suffix
# were generated from chat GPT3.5 on 2023-11-27.
# many of them appear to right, but many probably aren't
# the best explanation. Double check yourself.
SUFFIX_ACRONYMS = set([
    '(ret)',  # Retired
    '(vet)',  # Veteran
    '8-vsb',  # 8-level vestigial sideband (technical term in signal processing)
    'aas',    # Associate of Applied Science
    'aba',    # American Bar Association
    'abc',    # American Board of Certification
    'abd',    # American Board of Dermatology
    'abpp',   # American Board of Professional Psychology
    'abr',    # American Board of Radiology
    'aca',    # Associate of the Institute of Chartered Accountants
    'acas',   # Associate of the Casualty Actuarial Society
    'ace',    # Adobe Certified Expert
    'acha',   # Associate of the Casualty Actuarial Society
    'acp',    # Agile Certified Practitioner
    'ae',     # Associate Engineer
    'aem',    # Adobe Experience Manager
    'afasma', # Associate Fellow of the Aerospace Medical Association
    'afc',    # Associate Fellow of the Conference
    'afm',    # Associate in Facilities Management
    'agsf',   # Associate in General Studies of Fine Arts
    'aia',    # American Institute of Architects
    'aicp',   # American Institute of Certified Planners
    'ala',    # Associate of the Library Association
    'alc',    # Associate Life and Health Claims
    'alp',    # Associate Landscape Professional
    'am',     # Associate Member
    'amd',    # Advanced Micro Devices
    'ame',    # Associate Member of the Institution of Engineers
    'amieee', # Associate Member of the Institute of Electrical and Electronics Engineers
    'ams',    # American Mathematical Society
    'aphr',   # Associate Professional in Human Resources
    'apn aprn',  # Advanced Practice Nurse or Advanced Practice Registered Nurse
    'apr',    # Accredited in Public Relations
    'apss',   # Associate Professional Soil Scientist
    'aqp',    # Associate in Quality Provision
    'arm',    # Associate in Risk Management
    'arrc',   # Associate of the Royal Red Cross
    'asa',    # Associate of the Society of Actuaries
    'asc',    # Associate of Science
    'asid',   # American Society of Interior Designers
    'asla',   # American Society of Landscape Architects
    'asp',    # Associate Safety Professional
    'atc',    # Athletic Trainer, Certified
    'awb',    # American Writers and Artists Institute
    'bca',    # Bachelor of Computer Applications
    'bcl',    # Bachelor of Civil Law
    'bcss',   # Bachelor of Science in Computer Science
    'bds',    # Bachelor of Dental Surgery
    'bem',    # Bachelor of Environmental Management
    'bls-i',  # Basic Life Support for Infants (medical certification)
    'bpe',    # Bachelor of Physical Education
    'bpi',    # Building Performance Institute
    'bpt',    # Bachelor of Physiotherapy
    'bt',     # Bachelor of Technology
    'btcs',   # Board Certified in Trauma Stress
    'bts',    # Bachelor of Theological Studies
    'cacts',  # Certified Alarm and Central Station Technician
    'cae',    # Certified Association Executive
    'caha',   # Certified Affordable Housing Administrator
    'caia',   # Chartered Alternative Investment Analyst
    'cams',   # Certified Anti-Money Laundering Specialist
    'cap',    # Certified Administrative Professional
    'capa',   # Certified Accounts Payable Associate
    'capm',   # Certified Associate in Project Management
    'capp',   # Certified Asset Protection Professional
    'caps',   # Certified Aging in Place Specialist
    'caro',   # Certified Agile Release Owner
    'cas',    # Casualty Actuarial Society
    'casp',   # CompTIA Advanced Security Practitioner
    'cb',     # Citizen's Band (radio communication)
    'cbe',    # Certified Business Economist
    'cbm',    # Certified Business Manager
    'cbne',   # Certified Broadcast Networking Engineer
    'cbnt',   # Certified Broadcast Networking Technologist
    'cbp',    # Certified Business Process Professional
    'cbrte',  # Certified Biomedical Equipment Technician
    'cbs',    # Certified Bariatric Surgeon
    'cbsp',   # Certified Business Services Professional
    'cbt',    # Cognitive Behavioral Therapy
    'cbte',   # Certified Broadcast Television Engineer
    'cbv',    # Certified Business Valuator
    'cca',    # Certified Coding Associate
    'ccc',    # Certified Cardiographic Technician
    'ccca',   # Certified Construction Contract Administrator
    'cccm',   # Certified Commercial Contracts Manager
    'cce',    # Certified Cost Engineer
    'cchp',   # Certified Correctional Health Professional
    'ccie',   # Cisco Certified Internetwork Expert
    'ccim',   # Certified Commercial Investment Member
    'cciso',  # Certified Chief Information Security Officer
    'ccm',    # Certified Case Manager
    'ccmt',   # Certified Complementary Medical Therapist
    'ccna',   # Cisco Certified Network Associate
    'ccnp',   # Cisco Certified Network Professional
    'ccp',    # Certified Computing Professional
    'ccp-c',  # Certified Credit Professional - Canada
    'ccpr',   # Certified Childbirth Educator
    'ccs',    # Certified Coding Specialist
    'ccufc',  # Certified Credit Union Financial Counselor
    'cd',     # Compact Disc
    'cdal',   # Certified Data Architecture Leader
    'cdfm',   # Certified Defense Financial Manager
    'cdmp',   # Certified Data Management Professional
    'cds',    # Certified Dental Surgeon
    'cdt',    # Certified Dental Technician
    'cea',    # Certified Energy Auditor
    'ceas',   # Certified Ergonomics Assessment Specialist
    'cebs',   # Certified Employee Benefit Specialist
    'ceds',   # Certified E-Discovery Specialist
    'ceh',    # Certified Ethical Hacker
    'cela',   # Council of Educators in Landscape Architecture
    'cem',    # Certified Energy Manager
    'cep',    # Certified Ecotourism Professional
    'cera',   # Chartered Enterprise Risk Analyst
    'cet',    # Certified Engineering Technologist
    'cfa',    # Chartered Financial Analyst
    'cfc',    # Certified Financial Consultant
    'cfcc',   # Certified Forensic Computer Examiner
    'cfce',   # Certified Computer Examiner
    'cfcm',   # Certified Federal Contracts Manager
    'cfe',    # Certified Fraud Examiner
    'cfeds',  # Certified Federal Surveyor
    'cfi',    # Certified Flight Instructor
    'cfm',    # Certified Facility Manager
    'cfp',    # Certified Financial Planner
    'cfps',   # Certified Fire Protection Specialist
    'cfr',    # Code of Federal Regulations
    'cfre',   # Certified Fund Raising Executive
    'cga',    # Certified General Accountant
    'cgap',   # Certified Government Auditing Professional
    'cgb',    # Certified Graduate Builder
    'cgc',    # Certified General Contractor
    'cgfm',   # Certified Government Financial Manager
    'cgfo',   # Certified Government Finance Officer
    'cgm',    # Certified Green Master
    'cgma',   # Chartered Global Management Accountant
    'cgp',    # Certified Green Professional
    'cgr',    # Certified Government Relocation Specialist
    'cgsp',   # Certified Guest Service Professional
    'ch',     # Certified Herbalist
    'ch',     # Church
    'cha',    # Certified Hotel Administrator
    'chba',   # Certified Healthy Building Advocate
    'chdm',   # Certified Healthcare Digital Marketer
    'che',    # Certified Hospitality Educator
    'ches',   # Certified Health Education Specialist
    'chfc',   # Chartered Financial Consultant
    'chfc',   # Certified Health Fitness Specialist
    'chi',    # Certified Herbalist Instructor
    'chmc',   # Certified Healthcare Marketing Consultant
    'chmm',   # Certified Hazardous Materials Manager
    'chp',    # Certified Hospice Professional
    'chpa',   # Certified Hazardous Products Advisor
    'chpe',   # Certified High Performance Expert
    'chpln',  # Certified Heritage Preservation Planner
    'chpse',  # Certified Healthcare Patient Safety Executive
    'chrm',   # Certified Human Resources Manager
    'chsc',   # Certified Health and Safety Consultant
    'chse',   # Certified Healthcare Simulation Educator
    'chse-a', # Certified Healthcare Simulation Educator-Advanced
    'chsos',  # Certified Healthcare Simulation Operations Specialist
    'chss',   # Certified Homeland Security Specialist
    'cht',    # Certified Hand Therapist
    'cia',    # Certified Internal Auditor
    'cic',    # Certified Insurance Counselor
    'cie',    # Certified Irrigation Evaluator
    'cig',    # Certified Insurance Guaranty Association
    'cip',    # Certified Information Professional
    'cipm',   # Certified Information Privacy Manager
    'cips',   # Certified International Property Specialist
    'ciro',   # Certified Information Risk Officer
    'cisa',   # Certified Information Systems Auditor
    'cism',   # Certified Information Security Manager
    'cissp',  # Certified Information Systems Security Professional
    'cla',    # Certified Leasing Agent
    'clsd',   # Certified Leasing Specialist in Dispositions
    'cltd',   # Certified in Logistics, Transportation, and Distribution
    'clu',    # Chartered Life Underwriter
    'cm',     # Certified Manager
    'cma',    # Certified Management Accountant
    'cmas',   # Certified Medical Administrative Specialist
    'cmc',    # Certified Management Consultant
    'cmfo',   # Certified Municipal Finance Officer
    'cmg',    # Certified Master Groomer
    'cmp',    # Certified Meeting Professional
    'cms',    # Certified Medical Scribe Specialist
    'cmsp',   # Certified Manager of Software Process
    'cmt',    # Certified Massage Therapist
    'cna',    # Certified Nursing Assistant
    'cnm',    # Certified Nurse-Midwife
    'cnp',    # Certified Nurse Practitioner
    'cp',     # Certified Paralegal
    'cp-c',   # Certified Phlebotomy Technician
    'cpa',    # Certified Public Accountant
    'cpacc',  # Certified Professional in Accessibility Core Competencies
    'cpbe',   # Certified Professional Broadcast Engineer
    'cpcm',   # Certified Professional Contracts Manager
    'cpcu',   # Chartered Property Casualty Underwriter
    'cpe',    # Continuing Professional Education
    'cpfa',   # Certified Personal Finance Advisor
    'cpfo',   # Certified Public Finance Officer
    'cpg',    # Certified Professional Geologist
    'cph',    # Certified in Public Health
    'cpht',   # Certified Pharmacy Technician
    'cpim',   # Certified in Production and Inventory Management
    'cpl',    # Certified Professional Logistician
    'cplp',   # Certified Professional in Learning and Performance
    'cpm',    # Certified Property Manager
    'cpo',    # Chief People Officer
    'cpp',    # Certified Protection Professional
    'cppm',   # Certified Professional in Project Management
    'cprc',   # Certified Professional Rescuer: CPR
    'cpre',   # Certified Professional Requirements Engineer
    'cprp',   # Certified Psychiatric Rehabilitation Practitioner
    'cpsc',   # Certified Professional Soil Classifier
    'cpsi',   # Certified Playground Safety Inspector
    'cpss',   # Certified Privacy and Security Specialist
    'cpt',    # Certified Phlebotomy Technician
    'cpwa',   # Certified Private Wealth Advisor
    'crde',   # Certified Records Destruction Expert
    'crisc',  # Certified in Risk and Information Systems Control
    'crma',   # Certification in Risk Management Assurance
    'crme',   # Certified Revenue Management Executive
    'crna',   # Certified Registered Nurse Anesthetist
    'cro',    # Chief Risk Officer
    'crp',    # Certified Relocation Professional
    'crt',    # Certified Rehabilitation Counselor
    'crtt',   # Certified Respiratory Therapy Technician
    'csa',    # Certified Senior Advisor
    'csbe',   # Certified Sustainable Building Advisor
    'csc',    # Certified Safety Professional
    'cscp',   # Certified Supply Chain Professional
    'cscu',   # Certified Secure Computer User
    'csep',   # Certified Software Enhancement Professional
    'csi',    # Certified ScrumMaster
    'csm',    # Certified ScrumMaster
    'csp',    # Certified Safety Professional
    'cspo',   # Certified Scrum Product Owner
    'csre',   # Certified Software Requirements Engineer
    'csrte',  # Certified Specialist in Reverse Engineering
    'csslp',  # Certified Secure Software Lifecycle Professional
    'cssm',   # Certified Software Security Manager
    'cst',    # Certified Surgical Technologist
    'cste',   # Certified Software Test Engineer
    'ctbs',   # Certified Travel Business Specialist
    'ctfa',   # Certified Trust and Financial Advisor
    'cto',    # Chief Technology Officer
    'ctp',    # Certified Treasury Professional
    'cts',    # Certified Technology Specialist
    'cua',    # Certified Usability Analyst
    'cusp',   # Certified Usability Professional
    'cva',    # Certified Valuation Analyst
    'cva[22]',  # Certified Valuation Analyst
    'cvo',    # Certified Volunteer Ombudsman
    'cvp',    # Certified Valuation Professional
    'cvrs',   # Certified Vacation Rental Specialist
    'cwap',   # Certified Wireless Analysis Professional
    'cwb',    # Certified Welding Inspector
    'cwdp',   # Certified Wireless Design Professional
    'cwep',   # Certified Wireless Security Professional
    'cwna',   # Certified Wireless Network Administrator
    'cwne',   # Certified Wireless Network Expert
    'cwp',    # Certified Wellness Practitioner
    'cwsp',   # Certified Wireless Security Professional
    'cxa',    # Certified Exchange Administrator
    'cyds',   # Certified Youth Development Specialist
    'cysa',   # Certified Youth Sports Administrator
    'dabfm',  # Diplomate of the American Board of Family Medicine
    'dabvlm', # Diplomate of the American Board of Veterinary Laboratory Medicine
    'dacvim', # Diplomate of the American College of Veterinary Internal Medicine
    'dbe',    # Doctor of Business and Economics
    'dc',     # Doctor of Chiropractic
    'dcb',    # Diploma in Commercial Banking
    'dcm',    # Diploma in Civil Management
    'dcmg',   # Dame Commander of the Order of St Michael and St George
    'dcvo',   # Dame Commander of the Royal Victorian Order
    'dd',     # Doctor of Divinity
    'dds',    # Doctor of Dental Surgery
    'ded',    # Doctor of Education
    'dep',    # Doctor of Educational Psychology
    'dfc',    # Distinguished Flying Cross
    'dfm',    # Diploma in Financial Management
    'diplac', # Diploma in Accounting
    'diplom', # Diploma in Ophthalmology
    'djur',   # Diplomate of the Jurisprudence
    'dma',    # Doctor of Musical Arts
    'dmd',    # Doctor of Dental Medicine
    'dmin',   # Doctor of Ministry
    'dnp',    # Doctor of Nursing Practice
    'do',     # Doctor of Osteopathic Medicine
    'dpm',    # Doctor of Podiatric Medicine
    'dpt',    # Doctor of Physical Therapy
    'drb',    # Diploma in Reflexology and Body Massage
    'drmp',   # Diplomate of the Risk Management Professional
    'drph',   # Doctor of Public Health
    'dsc',    # Doctor of Science
    'dsm',    # Doctor of Sacred Music
    'dso',    # Doctor of Science in Optometry
    'dss',    # Diplomate in Social Studies
    'dtr',    # Dietetic Technician, Registered
    'dvep',   # Diploma in Veterinary Epidemiology and Public Health
    'dvm',    # Doctor of Veterinary Medicine
    'ea',     # Enrolled Agent
    'ed',     # Education
    'edd',    # Doctor of Education
    'ei',     # Engineer Intern
    'eit',    # Engineer in Training
    'els',    # Executive Leadership Summit
    'emd',    # Emergency Medical Dispatcher
    'emt-b',  # Emergency Medical Technician - Basic
    'emt-i/85',  # Emergency Medical Technician - Intermediate/85
    'emt-i/99',  # Emergency Medical Technician - Intermediate/99
    'emt-p',  # Emergency Medical Technician - Paramedic
    'enp',    # Emergency Nurse Practitioner
    'erd',    # Electronic Roadside Display
    'esq',    # Esquire
    'evp',    # Executive Vice President
    'faafp',  # Fellow of the American Academy of Family Physicians
    'faan',   # Fellow of the American Academy of Nursing
    'faap',   # Fellow of the American Academy of Pediatrics
    'fac-c',  # Fellow of the American College of Cardiology
    'facc',   # Fellow of the American College of Cardiology
    'facd',   # Fellow of the American College of Dentists
    'facem',  # Fellow of the Australasian College for Emergency Medicine
    'facep',  # Fellow of the American College of Emergency Physicians
    'facha',  # Fellow of the American College of Healthcare Architects
    'facofp', # Fellow of the American College of Foot and Ankle Orthopedics and Medicine
    'facog',  # Fellow of the American College of Obstetricians and Gynecologists
    'facp',   # Fellow of the American College of Physicians
    'facph',  # Fellow of the American College of Public Health
    'facs',   # Fellow of the American College of Surgeons
    'faia',   # Fellow of the American Institute of Architects
    'faicp',  # Fellow of the American Institute of Certified Planners
    'fala',   # Fellow of the American Laryngological Association
    'fashp',  # Fellow of the American Society of Health-System Pharmacists
    'fasid',  # Fellow of the American Society of Interior Designers
    'fasla',  # Fellow of the American Society of Landscape Architects
    'fasma',  # Fellow of the Aerospace Medical Association
    'faspen', # Fellow of the American Society for Parenteral and Enteral Nutrition
    'fca',    # Fellow of the Institute of Chartered Accountants
    'fcas',   # Fellow of the Casualty Actuarial Society
    'fcela',  # Fellow of the Council of Educators in Landscape Architecture
    'fd',     # Fellow of Design
    'fec',    # Family Enterprise Consultant
    'fhames', # Fellow of the Higher Academy of Medical Educators
    'fic',    # Fellow of the Institute of Chartered Accountants
    'ficf',   # Fellow of the Institute of Chartered Foresters
    'fieee',  # Fellow of the Institute of Electrical and Electronics Engineers
    'fmp',    # Facility Management Professional
    'fmva',   # Financial Modeling and Valuation Analyst
    'fnss',   # Fellow of the National Speleological Society
    'fp&a',   # Financial Planning and Analysis
    'fp-c',   # Flight Paramedic-Certified
    'fpc',    # Financial Planning Certificate
    'frm',    # Financial Risk Manager
    'fsa',    # Fellow of the Society of Actuaries
    'fsdp',   # Fellow, Society of Design Professionals
    'fws',    # Federal Waterfowl Stamp
    'gaee[14]',  # Graduate of the Australian Institute of Company Directors
    'gba',       # General Business Administration
    'gbe',       # General Business Education
    'gc',        # Grand Cross
    'gcb',       # Grand Cross of the Bath
    'gchs',      # Grand Cross of the Holy Sepulchre
    'gcie',      # Grand Commander of the Order of the Indian Empire
    'gcmg',      # Grand Cross of the Order of St Michael and St George
    'gcsi',      # Grand Cross of the Order of the Star of India
    'gcvo',      # Grand Cross of the Royal Victorian Order
    'gisp',      # Geographic Information Systems Professional
    'git',       # Geographic Information Technician
    'gm',        # General Manager
    'gmb',       # General, Municipal, and Boilermakers
    'gmr',       # General Maintenance and Repair
    'gphr',      # Global Professional in Human Resources
    'gri',       # Global Reporting Initiative
    'grp',       # Graduate Real Property
    'gsmieee',   # Graduate Student Member of the IEEE
    'hccp',      # Housing Credit Certified Professional
    'hrs',       # Human Resources Specialist
    'iaccp',     # International Association of Cross-Cultural Psychology
    'iaee',      # International Association for Energy Economics
    'iccm-d',    # International Conference on Conceptual Modeling - Doctoral Symposium
    'iccm-f',    # International Conference on Conceptual Modeling - Forum
    'idsm',      # Industrial Data Space Management
    'ifgict',    # International Federation of Global & Information Communication Technology
    'iom',       # Institute of Medicine
    'ipep',      # Integrated Project Execution Plan
    'ipm',       # Institute of Project Management
    'iso',       # International Organization for Standardization
    'issp-csp',  # Information Systems Security Professional - Certified Information Systems Security Professional
    'issp-sa',   # Information Systems Security Professional - Systems Security Architecture
    'itil',      # Information Technology Infrastructure Library
    'jd',        # Juris Doctor
    'jp',        # Justice of the Peace
    'kbe',       # Knight Commander of the Order of the British Empire
    'kcb',       # Knight Commander of the Order of the Bath
    'kchs/dchs', # Knight/Dame Commander of the Order of St John
    'kcie',      # Knight Commander of the Order of the Indian Empire
    'kcmg',      # Knight Commander of the Order of St Michael and St George
    'kcsi',      # Knight Commander of the Order of the Star of India
    'kcvo',      # Knight Commander of the Royal Victorian Order
    'kg',        # Knight of the Garter
    'khs/dhs',   # Knight/Dame of the Order of St John
    'kp',        # Knight of the Order of St Patrick
    'kt',        # Knight of the Thistle
    'lac',       # Licensed Acupuncturist
    'lcmt',      # Licensed Massage Therapist
    'lcpc',      # Licensed Clinical Professional Counselor
    'lcsw',      # Licensed Clinical Social Worker
    'leed ap',   # Leadership in Energy and Environmental Design Accredited Professional
    'lg',        # Lieutenant Governor
    'litk',      # Licensed International Tour Manager
    'litl',      # Licensed International Tour Leader
    'litp',      # Licensed International Tour Planner
    'llm',       # Legum Magister (Master of Laws)
    'lm',        # Licensed Midwife
    'lmsw',      # Licensed Master Social Worker
    'lmt',       # Licensed Massage Therapist
    'lp',        # Licensed Psychologist
    'lpa',       # Licensed Psychological Associate
    'lpc',       # Licensed Professional Counselor
    'lpn',       # Licensed Practical Nurse
    'lpss',      # Licensed Psychological Service Specialist
    'lsi',       # Lighting Specialist I
    'lsit',      # Land Surveyor in Training
    'lt',        # Lieutenant
    'lvn',       # Licensed Vocational Nurse
    'lvo',       # Lady of the Royal Victorian Order
    'lvt',       # Licensed Veterinary Technician
    'ma',        # Master of Arts
    'maaa',      # Member of the American Academy of Actuaries
    'mai',       # Member, Appraisal Institute
    'mba',       # Master of Business Administration
    'mbe',       # Member of the Order of the British Empire
    'mbs',       # Master of Business Studies
    'mc',        # Master of Ceremonies
    'mcct',      # Master Certified Coach Trainer
    'mcdba',     # Microsoft Certified Database Administrator
    'mches',     # Master Certified Health Education Specialist
    'mcm',       # Master of Christian Ministry
    'mcp',       # Microsoft Certified Professional
    'mcpd',      # Microsoft Certified Professional Developer
    'mcsa',      # Microsoft Certified Solutions Associate
    'mcsd',      # Microsoft Certified Solutions Developer
    'mcse',      # Microsoft Certified Systems Engineer
    'mct',       # Microsoft Certified Trainer
    'md',        # Doctor of Medicine
    'mdiv',      # Master of Divinity
    'mem',       # Member of the Institution of Mechanical Engineers
    'mfa',       # Master of Fine Arts
    'micp',      # Master Instructor in Crisis Prevention
    'mieee',     # Member of the Institute of Electrical and Electronics Engineers
    'mirm',      # Master in Insurance and Risk Management
    'mle',       # Master of Legal Studies
    'mls',       # Master of Library Science
    'mlse',      # Master of Legal Studies in Entertainment Law
    'mlt',       # Medical Laboratory Technologist
    'mm',        # Master of Music
    'mmad',      # Master of Management in Aviation and Defense
    'mmas',      # Master of Military Art and Science
    'mnaa',      # Member of the National Academy of Arbitrators
    'mnae',      # Member of the National Academy of Engineering
    'mp',        # Member of Parliament
    'mpa',       # Master of Public Administration
    'mph',       # Master of Public Health
    'mpse',      # Motion Picture Sound Editors
    'mra',       # Member of the Royal Academy
    'ms',        # Master of Science
    'msa',       # Master of Science in Administration
    'msc'        # Master of Science
    'mscmsm',    # Master of Science in Computer Science and Management
    'msm',       # Master of Sacred Music
    'mt',        # Medical Technologist
    'mts',       # Master of Theological Studies
    'mvo',       # Member of the Royal Victorian Order
    'nbc-his',   # National Board Certified Hearing Instrument Specialist
    'nbcch',     # National Board Certified Clinical Hypnotherapist
    'nbcch-ps',  # National Board Certified Clinical Hypnotherapist - Pain Specialist
    'nbcdch',    # National Board Certified Dental Ceramist
    'nbcdch-ps', # National Board Certified Dental Ceramist - Pain Specialist
    'nbcfch',    # National Board Certified Foot Care
    'nbcfch-ps', # National Board Certified Foot Care - Pain Specialist
    'nbct',      # National Board Certified Teacher
    'ncarb',     # National Council of Architectural Registration Boards
    'nccp',      # National Certified Counselor
    'ncidq',     # National Council for Interior Design Qualification
    'ncps',      # National Certified Peer Specialist
    'ncso',      # National Certified Sign Language Interpreter for the Deaf
    'ncto',      # National Car Test Operator
    'nd',        # Doctor of Naturopathic Medicine
    'ndtr',      # Nutrition and Dietetics Technician, Registered
    'nicet i',   # National Institute for Certification in Engineering Technologies - Level I
    'nicet ii',  # National Institute for Certification in Engineering Technologies - Level II
    'nicet iii', # National Institute for Certification in Engineering Technologies - Level III
    'nicet iv',  # National Institute for Certification in Engineering Technologies - Level IV
    'nmd',       # Naturopathic Medical Doctor
    'np',        # Nurse Practitioner
    'np[18]',    # Nurse Practitioner
    'nraemt',    # National Registry Advanced Emergency Medical Technician
    'nremr',     # National Registry Emergency Medical Responder
    'nremt',     # National Registry Emergency Medical Technician
    'nrp',       # Neonatal Resuscitation Program
    'obe',       # Officer of the Order of the British Empire
    'obi',       # Officer of the Order of the Bath
    'oca',       # Oracle Certified Associate
    'ocm',       # Organizational Change Management
    'ocp',       # Oracle Certified Professional
    'od',        # Doctor of Optometry
    'om',        # Osteopathic Manipulative Medicine
    'oscp',      # Offensive Security Certified Professional
    'ot',        # Occupational Therapist
    'pa-c',      # Physician Assistant - Certified
    'pcc',       # Professional Certified Coach
    'pci',       # Payment Card Industry
    'pe',        # Professional Engineer
    'pfmp',      # Portfolio Management Professional
    'pg',        # Postgraduate
    'pgmp',      # Program Management Professional
    'ph',        # Doctor of Philosophy
    'pharmd',    # Doctor of Pharmacy
    'phc',       # Palliative and Hospice Care
    'phd',       # Doctor of Philosophy
    'phr',       # Professional in Human Resources
    'phrca',     # Professional in Human Resources - California
    'pla',       # Professional Landman
    'pls',       # Professional Land Surveyor
    'pmc',       # Project Management Consultant
    'pmi-acp',   # Project Management Institute - Agile Certified Practitioner
    'pmp',       # Project Management Professional
    'pp',        # Personal Property
    'pps',       # Professional Plan Sponsor
    'prm',       # Professional Risk Manager
    'psm i',     # Professional Scrum Master I
    'psm ii',    # Professional Scrum Master II
    'psm',       # Professional Scrum Master
    'psp',       # Project Management Professional
    'psyd',      # Doctor of Psychology
    'pt',        # Physical Therapist
    'pta',       # Physical Therapist Assistant
    'qam',       # Quality Assurance Manager
    'qc',        # Quality Control
    'qcsw',      # Qualified Clinical Social Worker
    'qfsm',      # Qualified Fire Safety Manager
    'qgm',       # Qualified General Manager
    'qpm',       # Qualified Project Manager
    'qsd',       # Qualified Security Design
    'qsp',       # Qualified Security Professional
    'ra',        # Registered Architect
    'rai',       # Registered Accessibility Inspector
    'rba',       # Registered Building Architect
    'rci',       # Registered Communications Distribution Designer
    'rcp',       # Respiratory Care Practitioner
    'rd',        # Registered Dietitian
    'rdcs',      # Registered Diagnostic Cardiac Sonographer
    'rdh',       # Registered Dental Hygienist
    'rdms',      # Registered Diagnostic Medical Sonographer
    'rdn',       # Registered Dietitian Nutritionist
    'res',       # Registered Environmental Specialist
    'rfp',       # Request for Proposal
    'rhca',      # Red Hat Certified Architect
    'rid',       # Registered Interior Designer
    'rls',       # Registered Land Surveyor
    'rmsks',     # Registered Musculoskeletal Sonographer
    'rn',        # Registered Nurse
    'rp',        # Registered Pharmacist
    'rpa',       # Registered Physician Assistant
    'rph',       # Registered Pharmacist
    'rpl',       # Registered Professional Landman
    'rrc',       # Registered Roof Consultant
    'rrt',       # Registered Respiratory Therapist
    'rrt-accs',  # Registered Respiratory Therapist - Adult Critical Care Specialist
    'rrt-nps',   # Registered Respiratory Therapist - Neonatal/Pediatric Specialist
    'rrt-sds',   # Registered Respiratory Therapist - Sleep Disorders Specialist
    'rtrp',      # Registered Tax Return Preparer
    'rvm',       # Registered Vascular Technologist
    'rvt',       # Registered Vascular Technologist
    'sa',        # System Administrator
    'same',      # Society of American Military Engineers
    'sasm',      # Six Sigma Master Black Belt
    'sccp',      # Supply Chain Certified Professional
    'scmp',      # Supply Chain Management Professional
    'se',        # Systems Engineer
    'secb',      # Systems Engineering Capability Baseline
    'sfp',       # Synchronous Frame Protocol
    'sgm',       # Synchronous Graphics Module
    'shrm-cp',   # Society for Human Resource Management - Certified Professional
    'shrm-scp',  # Society for Human Resource Management - Senior Certified Professional
    'si',        # Systems Integrator
    'siie',      # Senior Member of the Institute of Industrial Engineers
    'smieee',    # Senior Member of the Institute of Electrical and Electronics Engineers
    'sphr',      # Senior Professional in Human Resources
    'sra',       # Society for Risk Analysis
    'sscp',   # System Security Certified Practitioner
    'stmieee',  # IEEE Standards for Software Test Documentation
    'tbr-ct',  # Test Bed Readiness - Conformance Testing
    'td',  # Technical Documentation
    'thd',  # Total Harmonic Distortion
    'thm',  # Thermal
    'ud',  # User Documentation
    'usa',  # United States of America
    'usaf',  # United States Air Force
    'usar',  # United States Army Reserve
    'uscg',  # United States Coast Guard
    'usmc',  # United States Marine Corps
    'usn',  # United States Navy
    'usnr',  # United States Navy Reserve
    'uxc',  # User Experience Consultant
    'uxmc',  # User Experience Design MasterClass
    'vc',  # Venture Capital
    'vc',  # Video Conferencing or Virtual Currency (context-dependent)
    'vcp',  # Video Content Producer
    'vd',  # Virtual Desktop
    'vrd',  # Virtual Reality Development
])
"""

Post-nominal acronyms. Titles, degrees and other things people stick after their name
that may or may not have periods between the letters. The parser removes periods
when matching against these pieces.

"""
