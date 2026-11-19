import unittest

from pydantic import ValidationError

from ai_reverse_user_story.models import BusinessRule, Evidence, Feature, UserStory


def make_feature() -> Feature:
    return Feature(
        name="Apply coupon at checkout",
        module="Basket and Orders",
        user_story=UserStory(
            actor="a customer at checkout",
            goal="to enter a coupon code",
            benefit="I get a discount on my order",
        ),
        rules=[
            BusinessRule(
                statement="An expired coupon is rejected with an error message.",
                evidence=[Evidence(file="routes/coupon.ts", start_line=10, end_line=24)],
            ),
            BusinessRule(
                statement="A valid coupon reduces the order total.",
                evidence=[Evidence(file="routes/basket.ts", start_line=40, end_line=60)],
            ),
        ],
        open_questions=["Can coupons be combined?"],
    )


class ModelTests(unittest.TestCase):
    def test_rule_without_evidence_is_rejected(self):
        with self.assertRaises(ValidationError):
            BusinessRule(statement="Users must be logged in.", evidence=[])

    def test_evidence_range_must_be_ordered(self):
        with self.assertRaises(ValidationError):
            Evidence(file="a.ts", start_line=20, end_line=10)

    def test_evidence_lines_start_at_one(self):
        with self.assertRaises(ValidationError):
            Evidence(file="a.ts", start_line=0, end_line=3)

    def test_feature_requires_at_least_one_rule(self):
        with self.assertRaises(ValidationError):
            Feature(
                name="Empty",
                module="m",
                user_story=UserStory(actor="a user", goal="to do it", benefit="it works"),
                rules=[],
            )

    def test_user_story_text(self):
        story = make_feature().user_story
        self.assertEqual(
            story.as_text(),
            "As a customer at checkout, I want to enter a coupon code so that I get a discount on my order.",
        )

    def test_generator_payload_matches_test_case_generator_format(self):
        payload = make_feature().to_generator_payload()
        self.assertEqual(set(payload), {"title", "user_story", "acceptance_criteria"})
        self.assertEqual(payload["title"], "Apply coupon at checkout")
        self.assertEqual(
            payload["acceptance_criteria"],
            ["An expired coupon is rejected with an error message.", "A valid coupon reduces the order total."],
        )


if __name__ == "__main__":
    unittest.main()
