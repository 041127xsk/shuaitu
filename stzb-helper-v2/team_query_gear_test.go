package main

import (
	"os"
	"strings"
	"testing"
)

func TestTeamQueryGearParsingUsesRoleEverywhere(t *testing.T) {
	content := readTeamQueryVue(t)

	required := []string{
		"const parseGearInfo = (gearStr, role)",
		"parseGearInfo(team.gear, team.role).filter(Boolean)",
		"const gears = parseGearInfo(r.gear, r.role)",
		"v-for=\"(g, gi) in parseGearInfo(team.gear, team.role)\"",
		"getGearDisplay(team.gear, team.role, i-1)",
	}
	for _, needle := range required {
		if !strings.Contains(content, needle) {
			t.Fatalf("TeamQuery.vue missing %q", needle)
		}
	}
}

func TestTeamQueryCompactTableGearColumnMatchesHeaderOrder(t *testing.T) {
	content := readTeamQueryVue(t)

	headerGear := strings.Index(content, "<th>宝物</th>")
	headerStar := strings.Index(content, "<th>红度</th>")
	cellGear := strings.Index(content, "class=\"gear-cell\"")
	cellStar := strings.Index(content, "class=\"star-cell\"")

	if headerGear < 0 || headerStar < 0 || cellGear < 0 || cellStar < 0 {
		t.Fatalf("TeamQuery.vue missing compact table gear/star header or cell")
	}
	if headerGear > headerStar {
		t.Fatal("compact table header should keep gear before star")
	}
	if cellGear > cellStar {
		t.Fatal("compact table cells should keep gear before star to match header")
	}
}

func readTeamQueryVue(t *testing.T) string {
	t.Helper()
	data, err := os.ReadFile("frontend/src/pages/TeamQuery.vue")
	if err != nil {
		t.Fatalf("read TeamQuery.vue: %v", err)
	}
	return string(data)
}
