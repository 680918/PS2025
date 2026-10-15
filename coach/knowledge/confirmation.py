def confirm_candidate(candidate):

    candidate.status = "CONFIRMED"

    return candidate


def reject_candidate(candidate):

    candidate.status = "REJECTED"

    return candidate
