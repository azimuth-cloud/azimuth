def groupfinder(userid, request):
    if len(userid) > 0:
        return "user"
    else:
        return "unauthorised"