from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django_q.tasks import async_task

class ExecuteBotsView(APIView):
    """
    View to manually trigger bot execution via query parameters.
    Query Params:
    - family_id: ID of the bot family.
    - bot_id: ID of the bot within the family.
    - operate: (Optional) Boolean string to force 'operate' mode.
    """
    def get(self, request):
        family_id = request.query_params.get('family_id')
        bot_id = request.query_params.get('bot_id')
        operate = request.query_params.get('operate')

        if not family_id or not bot_id:
            return Response(
                {"error": "family_id and bot_id are required as query parameters."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            f_id = int(family_id)
            b_id = int(bot_id)
            force_op = None
            if operate is not None:
                force_op = str(operate).lower() == 'true'
        except ValueError:
            return Response(
                {"error": "family_id and bot_id must be valid integers."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        # Execute asynchronously with Django-Q
        async_task('apps.botops.ops.execute_bots.run_bot_force', f_id, b_id, operate=force_op if force_op is not None else False)
        #ex: http://api5000.dgen-systems.co/api/botops/execute?family_id=1&bot_id=3&operate=false
        return Response(
            {"message": f"Execution request for Bot {b_id} (Family {f_id}) accepted."}, 
            status=status.HTTP_202_ACCEPTED
        )
