data "panos_security_rules" "existing" {}

data "panos_security_rule" "all" {
  for_each = toset(data.panos_security_rules.existing.listing)

  name     = each.value
  rulebase = "pre-rulebase"
  vsys     = "vsys1"
}

output "security_rules_json" {
  description = "All retreived PAN-OS Secuirty Rules in JSON Format"
  value = jsonencode({
    for name, rule in data.panos_security_rule.all :
    name => rule.rule
  })
}