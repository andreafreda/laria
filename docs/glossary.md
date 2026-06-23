# LARIA — naming glossary (IT → EN)

Canonical English names for domains, modules, tables and concepts. All LARIA code,
identifiers, DB tables and APIs use the **EN** column. The IT column is the HARIA source
term, for reference while porting. Freeze new terms here before using them in code.

## Modules
| HARIA (IT) | LARIA (EN) |
|---|---|
| economia | finance |
| food_diary / cibo | food |
| agenda | agenda |
| bollette | utilities |
| news | news |
| web_search | web_search |
| multi_user | users |

## Finance domain
| IT | EN |
|---|---|
| conto / conti | account / accounts |
| transazione / transazioni | transaction / transactions |
| movimenti (recenti) | (recent) transactions |
| categoria / categorie | category / categories |
| regola (auto-categorizzazione) | (categorization) rule |
| budget | budget |
| obiettivo / salvadanaio | savings goal |
| accantonato | saved (amount) |
| spese | expenses |
| entrate | income |
| saldo | balance |
| intestatario | owner |
| trasferimento (giroconto) | transfer |
| prelievo contanti | cash withdrawal |
| riepilogo | summary / report |
| estratto conto / import | bank statement / import |

## Food domain
| IT | EN |
|---|---|
| profilo | profile |
| pasto / pasti | meal / meals |
| piano (pasti) | meal plan |
| dispensa | pantry |
| lista spesa | shopping list |
| idratazione | hydration |
| peso | weight |

## Utilities domain
| IT | EN |
|---|---|
| bolletta | bill |
| consumo | consumption |
| utenza | utility |

## Agent memory & misc
| IT | EN |
|---|---|
| nota / note | note / notes |
| riassunto | summary |
| promemoria | reminder |
| briefing | briefing |
| log errori | error log |

## DB table naming (proposal)
snake_case, module-prefixed:
`finance_accounts`, `finance_transactions`, `finance_categories`, `finance_rules`,
`finance_budgets`, `finance_goals`; `food_profiles`, `food_meals`, `food_meal_plan`,
`food_pantry`, `food_shopping`; `utilities_bills`; core/agent: `conversations`,
`summaries`, `notes`, `reminders`, `briefings`, `entity_cache`, `mqtt_topics`.
(Final table set depends on the memory re-engineering — see `plan.md`.)
