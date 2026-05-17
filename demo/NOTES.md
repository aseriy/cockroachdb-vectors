```sql
SELECT 'DELETE FROM ' || quote_ident(schema_name) || '.' || quote_ident(table_name) || ';' 
FROM [show tables];
```


```sql
SELECT 'SELECT count(*) FROM ' || quote_ident(schema_name) || '.' || quote_ident(table_name) || ';' 
FROM [show tables];
```


```sql
DELETE FROM aerospace_defense.compliance_standards;
DELETE FROM aerospace_defense.components_subsystems;
DELETE FROM aerospace_defense.maintenance_lifecycle_events;
DELETE FROM aerospace_defense.manufacturing_assembly;
DELETE FROM aerospace_defense.missions_operations;
DELETE FROM aerospace_defense.operational_incidents;
DELETE FROM aerospace_defense.platforms_systems;
DELETE FROM aerospace_defense.security_threat_events;
DELETE FROM aerospace_defense.supply_chain_entities;
DELETE FROM aerospace_defense.telemetry_sensor_data;
DELETE FROM ai_customer_experience.ai_models_capabilities;
DELETE FROM ai_customer_experience.analytics_metrics;
DELETE FROM ai_customer_experience.automation_workflows;
DELETE FROM ai_customer_experience.compliance_policies;
DELETE FROM ai_customer_experience.customer_profiles;
DELETE FROM ai_customer_experience.interaction_channels;
DELETE FROM ai_customer_experience.interaction_events;
DELETE FROM ai_customer_experience.knowledge_content;
DELETE FROM ai_customer_experience.operational_incidents;
DELETE FROM ai_customer_experience.recommendation_personalization;
DELETE FROM automotive_ev.charging_infrastructure;
DELETE FROM automotive_ev.compliance_standards;
DELETE FROM automotive_ev.components_subsystems;
DELETE FROM automotive_ev.manufacturing_processes;
DELETE FROM automotive_ev.mobility_services;
DELETE FROM automotive_ev.operational_incidents;
DELETE FROM automotive_ev.software_systems;
DELETE FROM automotive_ev.supply_chain_entities;
DELETE FROM automotive_ev.telemetry_vehicle_data;
DELETE FROM automotive_ev.vehicles_platforms;
DELETE FROM blockchain_crypto.blockchain_networks;
DELETE FROM blockchain_crypto.digital_assets;
DELETE FROM blockchain_crypto.governance_mechanisms;
DELETE FROM blockchain_crypto.identity_name_services;
DELETE FROM blockchain_crypto.infrastructure_services;
DELETE FROM blockchain_crypto.protocol_interactions;
DELETE FROM blockchain_crypto.security_events;
DELETE FROM blockchain_crypto.smart_contracts;
DELETE FROM blockchain_crypto.transaction_events;
DELETE FROM blockchain_crypto.wallets_accounts;
DELETE FROM capital_markets.client_requests;
DELETE FROM capital_markets.compliance_policies;
DELETE FROM capital_markets.instruments;
DELETE FROM capital_markets.market_events;
DELETE FROM capital_markets.operational_incidents;
DELETE FROM capital_markets.research_commentary;
DELETE FROM capital_markets.trade_lifecycle_events;
DELETE FROM cloud_infrastructure.access_identity_controls;
DELETE FROM cloud_infrastructure.compute_resources;
DELETE FROM cloud_infrastructure.configuration_state;
DELETE FROM cloud_infrastructure.cost_usage_records;
DELETE FROM cloud_infrastructure.deployment_events;
DELETE FROM cloud_infrastructure.networking_components;
DELETE FROM cloud_infrastructure.observability_metrics;
DELETE FROM cloud_infrastructure.operational_incidents;
DELETE FROM cloud_infrastructure.security_events;
DELETE FROM cloud_infrastructure.storage_resources;
DELETE FROM consumer_hospitality_retail.accommodations_inventory;
DELETE FROM consumer_hospitality_retail.booking_reservations;
DELETE FROM consumer_hospitality_retail.customer_profiles;
DELETE FROM consumer_hospitality_retail.experiences_offerings;
DELETE FROM consumer_hospitality_retail.fitness_services;
DELETE FROM consumer_hospitality_retail.loyalty_rewards;
DELETE FROM consumer_hospitality_retail.monetization_events;
DELETE FROM consumer_hospitality_retail.operational_incidents;
DELETE FROM consumer_hospitality_retail.service_appointments;
DELETE FROM consumer_hospitality_retail.transactions;
DELETE FROM education_edtech.analytics_metrics;
DELETE FROM education_edtech.assessments_evaluations;
DELETE FROM education_edtech.compliance_policies;
DELETE FROM education_edtech.instructional_methods;
DELETE FROM education_edtech.learners_profiles;
DELETE FROM education_edtech.learning_content;
DELETE FROM education_edtech.learning_interactions;
DELETE FROM education_edtech.learning_programs;
DELETE FROM education_edtech.operational_incidents;
DELETE FROM education_edtech.platform_features;
DELETE FROM enterprise_software_services.analytics_metrics;
DELETE FROM enterprise_software_services.applications_services;
DELETE FROM enterprise_software_services.compliance_policies;
DELETE FROM enterprise_software_services.data_assets;
DELETE FROM enterprise_software_services.integrations;
DELETE FROM enterprise_software_services.operational_incidents;
DELETE FROM enterprise_software_services.security_controls;
DELETE FROM enterprise_software_services.system_events;
DELETE FROM enterprise_software_services.user_identities;
DELETE FROM enterprise_software_services.workflows_processes;
DELETE FROM financial_services.accounts;
DELETE FROM financial_services.client_requests;
DELETE FROM financial_services.compliance_policies;
DELETE FROM financial_services.customer_profiles;
DELETE FROM financial_services.fraud_risk_events;
DELETE FROM financial_services.lending_lifecycle_events;
DELETE FROM financial_services.operational_incidents;
DELETE FROM financial_services.payment_events;
DELETE FROM financial_services.product_configurations;
DELETE FROM financial_services.transactions;
DELETE FROM government_public_sector.analytics_metrics;
DELETE FROM government_public_sector.applications_requests;
DELETE FROM government_public_sector.case_management;
DELETE FROM government_public_sector.citizen_profiles;
DELETE FROM government_public_sector.compliance_controls;
DELETE FROM government_public_sector.data_records;
DELETE FROM government_public_sector.financial_operations;
DELETE FROM government_public_sector.operational_incidents;
DELETE FROM government_public_sector.public_services;
DELETE FROM government_public_sector.regulatory_policies;
DELETE FROM hardware_semiconductor.compliance_standards;
DELETE FROM hardware_semiconductor.deployment_hardware;
DELETE FROM hardware_semiconductor.firmware_software_interfaces;
DELETE FROM hardware_semiconductor.hardware_components;
DELETE FROM hardware_semiconductor.manufacturing_processes;
DELETE FROM hardware_semiconductor.operational_events;
DELETE FROM hardware_semiconductor.performance_metrics;
DELETE FROM hardware_semiconductor.security_features;
DELETE FROM hardware_semiconductor.semiconductor_products;
DELETE FROM hardware_semiconductor.supply_chain_entities;
DELETE FROM healthcare_life_sciences.analytics_metrics;
DELETE FROM healthcare_life_sciences.clinical_events;
DELETE FROM healthcare_life_sciences.clinical_services;
DELETE FROM healthcare_life_sciences.compliance_policies;
DELETE FROM healthcare_life_sciences.healthcare_operations;
DELETE FROM healthcare_life_sciences.medical_devices;
DELETE FROM healthcare_life_sciences.operational_incidents;
DELETE FROM healthcare_life_sciences.patient_profiles;
DELETE FROM healthcare_life_sciences.pharmaceuticals_biologics;
DELETE FROM healthcare_life_sciences.research_clinical_trials;
DELETE FROM logistics.compliance_regulations;
DELETE FROM logistics.cost_pricing;
DELETE FROM logistics.inventory_assets;
DELETE FROM logistics.operational_incidents;
DELETE FROM logistics.routing_planning;
DELETE FROM logistics.shipments_orders;
DELETE FROM logistics.supply_chain_entities;
DELETE FROM logistics.tracking_events;
DELETE FROM logistics.transportation_modes;
DELETE FROM logistics.warehouses_facilities;
```




For **Company X** — an aerospace and defense operator — merging all 10 tables:

```yaml
concept_domain: aerospace and defense data entity — platform, component, mission, telemetry signal, manufacturing process, maintenance event, supply chain entity, security event, compliance standard, or operational incident
concept_unit: entity
entry_count: 1180
concept_scope_examples: aircraft type, spacecraft system, unmanned system, mission platform, propulsion system, avionics module, sensor system, control system, surveillance mission, combat operation, transport mission, training exercise, flight telemetry, sensor reading, environmental measurement, assembly stage, fabrication process, quality control step, inspection event, repair action, overhaul, supplier role, manufacturer type, logistics provider, cyber intrusion, anomaly detection, threat alert, safety standard, certification requirement, system failure, mission disruption, equipment malfunction
instance_exclusion_rules: no IDs, no numbers, no dates, no people, no balances
trivial_variant_example: "military aircraft" vs "defense aircraft", "maintenance action" vs "repair event", "safety standard" vs "compliance requirement"
terminology_domain: aerospace, defense, industrial, supply chain, security, regulatory, operational
distinctness_criteria: function, structure, lifecycle stage, mission objective, signal type, process type, supply chain role, event type, requirement scope
domain_name: aerospace and defense
domain_scope: aircraft, spacecraft, drones, defense systems, mission platforms, engines, avionics, sensors, control systems, military operations, space missions, logistics missions, telemetry, diagnostics, fabrication, assembly, testing, integration, inspection, repair, overhaul, suppliers, manufacturers, contractors, cybersecurity, threat detection, safety certification, regulatory compliance, operational incidents
example_name: Aerospace and Defense Operations Record
example_description: A data entity representing any element of an aerospace or defense organization's operations — spanning platforms and components, missions, telemetry signals, manufacturing and maintenance processes, supply chain relationships, security events, compliance standards, and operational incidents.
```


1. What aircraft types, if any, does X design, manufacture, or operate?
2. Is X involved in spacecraft or satellite systems, and if so, in what capacity?
3. Does X develop unmanned or autonomous aerial platforms?
4. Is X involved in ground-based defense systems? What types?
5. Does X design or supply systems to naval platforms? In what capacity?
6. Is X involved in hypersonic programs, and if so, in what role?
7. Does X produce command and control systems?
8. Does X have electronic warfare systems in its portfolio?
9. Is X involved in rotary-wing platforms — manufacturing, maintenance, or both?
10. Does X serve commercial aerospace markets in addition to defense?
11. Is X involved in space launch systems, and in what capacity?
12. Does X produce reconnaissance or ISR platforms?
13. Does X manufacture propulsion systems or engines? For what platforms?
14. Is X involved in avionics development or integration?
15. Does X produce radar systems? At what level — component, subsystem, or integrated system?
16. Is X involved in navigation system development?
17. What structural components, if any, does X fabricate for aerospace platforms?
18. Does X design flight control systems?
19. Is X involved in airborne communication systems?
20. Does X produce power generation or distribution systems for aerospace platforms?
21. Is X involved in electro-optical or infrared (EO/IR) sensor systems?
22. Does X design or manufacture fuel systems for aerospace platforms?
23. Is X involved in targeting systems, and at what level?
24. Does X offer payload integration systems or services?
25. Is X involved in electronic countermeasure systems?
26. Does X manufacture landing gear systems?
27. Is X involved in thermal management systems for aerospace platforms?
28. What mission profiles, if any, are X's systems designed to support?
29. Does X's portfolio address surveillance or reconnaissance requirements?
30. Is X involved in combat or strike mission system development?
31. Does X support logistics, airlift, or transport mission requirements?
32. Is X involved in training programs or simulation systems?
33. Does X participate in space mission programs? In what role?
34. Is X involved in humanitarian or disaster response mission support?
35. Does X's technology serve maritime patrol or anti-submarine warfare requirements?
36. Is X involved in signals intelligence or electronic warfare mission systems?
37. Does X's portfolio address joint or multinational operation requirements?
38. What contested or denied environment requirements, if any, drive X's R&D?
39. Does X operate or develop flight telemetry systems?
40. What types of sensor data, if any, does X collect from deployed systems?
41. How does X manage real-time data from operational platforms?
42. Is X involved in environmental monitoring systems?
43. Does X use diagnostic telemetry for maintenance or prognostics?
44. Is X involved in tracking and positioning system development?
45. Does X integrate data from multiple sensor types? What approaches does it use?
46. Does X operate ground station infrastructure for telemetry processing?
47. What data transmission standards does X use for sensor data?
48. Is X applying AI or ML to telemetry or sensor data analysis?
49. Is X involved in satellite-based sensor systems?
50. What signal processing capabilities does X have in-house?
51. Where are X's manufacturing and assembly facilities located?
52. What fabrication processes does X use for its primary products?
53. Is X using advanced manufacturing technologies such as additive manufacturing or composite fabrication?
54. What system integration processes does X use?
55. What testing and qualification infrastructure does X operate?
56. What quality control standards govern X's manufacturing?
57. What production rates does X operate at for its primary products?
58. Does X operate any government-owned, contractor-operated (GOCO) facilities?
59. What automation or robotics, if any, does X use in production?
60. What materials science capabilities does X have in-house?
61. How does X manage configuration control through the production process?
62. Does X operate cleanroom or controlled-environment manufacturing?
63. Does X provide maintenance, repair, and overhaul (MRO) services? For what platforms?
64. What inspection programs does X operate for its products in the field?
65. Does X use condition-based or predictive maintenance approaches?
66. What depot-level maintenance capabilities does X hold?
67. Does X support forward-deployed or field-level maintenance?
68. Has X executed lifecycle extension programs for aging platforms?
69. How does X manage end-of-life or retirement of its products?
70. Does X operate parts obsolescence management programs?
71. Is X using digital twin or virtual maintenance capabilities?
72. Does X hold performance-based logistics (PBL) contracts?
73. How does X manage airworthiness across its installed customer base?
74. Does X run maintenance training programs for customer personnel?
75. Who are X's primary suppliers for critical components?
76. Are there single-source or sole-source dependencies in X's supply chain?
77. How does X manage risk for long-lead-time items?
78. What is X's domestic vs. international sourcing profile?
79. What export control constraints govern X's supply chain?
80. What subcontractors does X rely on for specialized work?
81. What raw material dependencies — specialty alloys, rare earth elements — does X carry?
82. How does X manage counterfeit parts risk?
83. What logistics or distribution infrastructure does X operate?
84. What supplier qualification and auditing processes does X use?
85. How does X respond to supply chain disruptions or critical shortages?
86. Does X maintain strategic stockpiles or buffer inventory for critical items?
87. What cybersecurity frameworks does X comply with?
88. Does X operate an insider threat program?
89. What physical security measures protect X's facilities and programs?
90. What supply chain cybersecurity risks has X identified or addressed?
91. What information security classification levels govern X's programs?
92. What incident response capabilities does X maintain?
93. Does X participate in threat intelligence sharing partnerships?
94. What anti-tamper or hardware security measures, if any, does X build into its products?
95. What security clearance levels does X's workforce hold?
96. Does X manage programs at the SAP or SCI classification level?
97. What security testing — red team, penetration testing — does X conduct on its systems?
98. Do foreign ownership, control, or influence (FOCI) considerations apply to X?
99. What software bill of materials (SBOM) practices does X follow?
100. What airworthiness certifications does X hold or pursue?
101. What quality management standards govern X's operations?
102. What environmental compliance programs does X operate?
103. What export licensing requirements apply to X's products?
104. What government contracting compliance obligations does X meet?
105. What safety certification standards apply to X's products?
106. What electromagnetic compatibility (EMC) standards do X's systems need to meet?
107. Does X pursue software airworthiness certification (DO-178C)?
108. Does X follow hardware assurance standards (DO-254)?
109. What MIL-SPEC or MIL-STD standards govern X's designs?
110. What ITAR categories, if any, cover X's products?
111. What ESG or sustainability reporting does X conduct?
112. What types of system failures have occurred across X's deployed products?
113. What mission disruptions have X's systems experienced in the field?
114. What equipment malfunctions have driven engineering changes at X?
115. What operational anomalies have triggered safety reviews at X?
116. Has X experienced fleet-wide groundings or operational stand-downs?
117. What communication or data system failures have impacted X's operations?
118. What supply chain-driven operational delays has X experienced?
119. Have manufacturing defects resulted in field recalls or retrofits at X?
120. What cybersecurity incidents have affected X's operational systems?
121. What safety or mishap reports has X filed with regulatory authorities?
122. What are X's primary business segments or divisions?
123. What percentage of X's revenue comes from government vs. commercial customers?
124. What international markets does X serve, and under what arrangements?
125. Is X primarily a prime contractor, a subcontractor, or does it operate in both roles?
126. Does X have significant classified program revenue?
127. Is X involved in commercial aerospace programs? In what capacity?
128. Does X operate a space or satellite business line?
129. Does X run a services business — MRO, training, logistics — alongside its products?
130. What R&D or internal investment programs is X currently funding?
131. What joint ventures or teaming arrangements is X currently part of?
132. Who are X's primary government customers?
133. Does X hold foreign military sales (FMS) relationships? With which nations?
134. What contract vehicles — IDIQ, GWAC — does X currently hold?
135. What programs of record anchor X's backlog?
136. What is X's fixed-price vs. cost-plus contract mix?
137. What next-generation programs is X competing for?
138. Does X have NATO or allied nation procurement relationships?
139. Does X conduct direct commercial sales, and in what areas?
140. Is X integrating autonomy or AI capabilities into its products or services?
141. Is X involved in directed energy programs?
142. Is X participating in hypersonic technology development?
143. Is X involved in space domain awareness?
144. What advanced materials research, if any, is X conducting?
145. Is X using model-based systems engineering (MBSE) in its programs?
146. Has X launched digital engineering or digital thread initiatives?
147. What open architecture standards, if any, does X adopt?
148. What simulation and modeling capabilities does X operate?
149. Is X investing in quantum or advanced computing research?
150. How large is X's engineering workforce relative to total headcount?
151. What security clearance pipeline challenges does X face?
152. Does X operate STEM recruiting or university partnership programs?
153. What labor relations or union agreements govern X's workforce?
154. What geographic concentration of skilled workforce does X depend on?
155. What is X's approximate annual revenue and funded backlog?
156. What is X's R&D spending as a percentage of revenue?
157. What acquisitions has X made in the last five years?
158. What divestitures or portfolio shaping has X executed?
159. What is X's funded vs. unfunded backlog profile?
160. What partnerships or strategic alliances define X's competitive position?
