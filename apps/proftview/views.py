from django.utils import timezone
from django.db.models import Sum, Q
from rest_framework import viewsets, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from apps.botops.models import BotAsset, Bot, Family, Broker, Transaction, PortfolioHistory
from .serializers import BotAssetSerializer, BotSerializer, FamilySerializer, BrokerSerializer
from .permissions import IsSuperUser, IsSuperUserOrReadOnly

class BotAssetViewSet(viewsets.ModelViewSet):
    queryset = BotAsset.objects.all()
    serializer_class = BotAssetSerializer
    permission_classes = [IsSuperUserOrReadOnly]

    def get_queryset(self):
        queryset = BotAsset.objects.all()
        family_id = self.request.query_params.get('family')
        bot_id = self.request.query_params.get('bot')
        broker_id = self.request.query_params.get('broker')

        if family_id and bot_id:
            queryset = queryset.filter(bot__family_id=family_id, bot_id=bot_id)
        elif family_id:
            queryset = queryset.filter(bot__family_id=family_id)
        elif bot_id:
            queryset = queryset.filter(bot_id=bot_id)

        if broker_id:
            queryset = queryset.filter(broker_id=broker_id)

        return queryset

class BotViewSet(viewsets.ModelViewSet):
    queryset = Bot.objects.all()
    serializer_class = BotSerializer
    permission_classes = [IsSuperUserOrReadOnly]

class FamilyViewSet(viewsets.ModelViewSet):
    queryset = Family.objects.all()
    serializer_class = FamilySerializer
    permission_classes = [IsSuperUserOrReadOnly]

class BrokerViewSet(viewsets.ModelViewSet):
    queryset = Broker.objects.all()
    serializer_class = BrokerSerializer
    permission_classes = [IsSuperUserOrReadOnly]

class BotAssetAggregatedView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        queryset = BotAsset.objects.all()
        bot_id = request.query_params.get('bot')
        broker_id = request.query_params.get('broker')
        family_id = request.query_params.get('family')

        if bot_id:
            queryset = queryset.filter(bot_id=bot_id)
        if broker_id:
            queryset = queryset.filter(broker_id=broker_id)
        if family_id:
            queryset = queryset.filter(bot__family_id=family_id)

        aggs = queryset.aggregate(
            cap_to_add_sum=Sum('cap_to_add'),
            cap_value_in_trade_sum=Sum('cap_value_in_trade', filter=~Q(qty_open=0)),
            pnl_un_sum=Sum('pnl_un'),
            PNL_sum=Sum('PNL'),
            coms_sum=Sum('coms'),
            trades_sum=Sum('trades'),
            cap_to_trade_sum=Sum('cap_to_trade', filter=Q(qty_open=0)),
            capAdded_sum=Sum('capAdded')
        )

        cap_to_add_sum = aggs['cap_to_add_sum'] or 0.0
        capAdded_sum = aggs['capAdded_sum'] or 0.0

        bot_ids = queryset.values_list('bot_id', flat=True).distinct()
        bot_aggs = Bot.objects.filter(id__in=bot_ids).aggregate(
            cap_no_asignado_sum=Sum('cap_no_asignado')
        )
        
        cap_no_asignado_sum = bot_aggs['cap_no_asignado_sum'] or 0.0
        total_capital_added = capAdded_sum + cap_no_asignado_sum
        cap_value_in_trade_sum = aggs['cap_value_in_trade_sum'] or 0.0
        cap_to_trade_sum = aggs['cap_to_trade_sum'] or 0.0
        total_cap_value = cap_value_in_trade_sum + cap_no_asignado_sum + cap_to_trade_sum+ cap_to_add_sum

        return Response({
            'cap_to_add_sum': cap_to_add_sum,
            'cap_value_in_trade_sum': cap_value_in_trade_sum,
            'pnl_un_sum': aggs['pnl_un_sum'] or 0.0,
            'PNL_sum': aggs['PNL_sum'] or 0.0,
            'coms_sum': aggs['coms_sum'] or 0.0,
            'trades_sum': aggs['trades_sum'] or 0.0,
            'cap_to_trade_sum': aggs['cap_to_trade_sum'] or 0.0,
            'capAdded_sum': capAdded_sum,
            'cap_no_asignado': cap_no_asignado_sum,
            'total_capital_added': total_capital_added,
            'total_cap_value': total_cap_value
        })

class AddCapitalToBotNoAsignView(APIView):
    permission_classes = [IsSuperUser]

    def post(self, request):
        bot_id = request.data.get('bot_id')
        amount = float(request.data.get('amount', 0))
        broker_id = request.data.get('broker_id')

        try:
            bot = Bot.objects.get(id=bot_id)
        except Bot.DoesNotExist:
            return Response({'error': 'Bot not found'}, status=404)

        # "el previous capital_added debe ser calculado con esta operacion que creamos 
        # en el view anterior 'total_capital_added = capAdded_sum + cap_no_asignado_sum' 
        # haciendo el queryset sin filtros"
        capAdded_sum = BotAsset.objects.aggregate(capAdded_sum=Sum('capAdded'))['capAdded_sum'] or 0.0
        cap_no_asignado_sum = Bot.objects.aggregate(cap_no_asignado_sum=Sum('cap_no_asignado'))['cap_no_asignado_sum'] or 0.0
        previous_capital_added = capAdded_sum + cap_no_asignado_sum

        # Adicionara el amount a lo que ya hay en el bot en el campo cap_no_asignado
        bot.cap_no_asignado += amount
        bot.save()

        # posterior_capital_added sumando a lo calculado el amount del body
        posterior_capital_added = previous_capital_added + amount

        # Creara un registro en el modelo Transaction de botops
        Transaction.objects.create(
            bot=bot,
            assetbot=None,
            capital=abs(amount),
            add_withdraw=1 if amount > 0 else 0, # El prompt dice: "si es positivo add_withdrwa 1"
            previous_capital_added=previous_capital_added,
            posterior_capital_added=posterior_capital_added,
            broker_id=broker_id,
            date=timezone.now().date()
        )

        return Response({
            'message': 'Capital added successfully',
            'bot_id': bot.id,
            'new_cap_no_asignado': bot.cap_no_asignado,
            'total_capital_added': posterior_capital_added
        })

class AddRemoveCapitalToAssetView(APIView):
    permission_classes = [IsSuperUser]

    def post(self, request):
        bot_asset_id = request.data.get('bot_asset_id')
        amount = float(request.data.get('amount', 0))

        try:
            bot_asset = BotAsset.objects.select_related('bot', 'broker').get(id=bot_asset_id)
        except BotAsset.DoesNotExist:
            return Response({'error': 'BotAsset not found'}, status=404)

        bot = bot_asset.bot
        today = timezone.now().date()

        # El previous_capital_added debe ser calculado como en el view que creamos anteriormente
        capAdded_sum = BotAsset.objects.aggregate(capAdded_sum=Sum('capAdded'))['capAdded_sum'] or 0.0
        cap_no_asignado_sum = Bot.objects.aggregate(cap_no_asignado_sum=Sum('cap_no_asignado'))['cap_no_asignado_sum'] or 0.0
        previous_capital_added = capAdded_sum + cap_no_asignado_sum

        if amount > 0:
            # Una cantidad positiva indica que estamos adicionando capital
            amount_from_bot = min(amount, bot.cap_no_asignado)
            amount_fresh = amount - amount_from_bot

            # Adicionara el amount a el campo de cap_to_add del botAsset
            bot_asset.cap_to_add += amount
            bot_asset.capAdded += amount
            
            # Actualiza la cantidad disponible en el Bot
            bot.cap_no_asignado -= amount_from_bot
            
            bot_asset.save()
            bot.save()

            # Transacciones
            if amount_from_bot > 0:
                Transaction.objects.create(
                    bot=bot,
                    assetbot=bot_asset,
                    capital=amount_from_bot,
                    add_withdraw=1,
                    move_between_bots=True,
                    previous_capital_added=previous_capital_added,
                    posterior_capital_added=previous_capital_added, # No cambia el total del sistema si se mueve entre bots
                    broker=bot_asset.broker,
                    date=today
                )
            
            if amount_fresh > 0:
                Transaction.objects.create(
                    bot=bot,
                    assetbot=bot_asset,
                    capital=amount_fresh,
                    add_withdraw=1,
                    move_between_bots=False,
                    previous_capital_added=previous_capital_added, # OJO: si hubo T1, este cálculo del sistema total podría cambiar
                    # Pero el total del sistema cambia con fresh capital:
                    posterior_capital_added=previous_capital_added + amount_fresh,
                    broker=bot_asset.broker,
                    date=today
                )

            return Response({
                'message': 'Capital added successfully',
                'bot_asset_id': bot_asset.id,
                'new_cap_to_add': bot_asset.cap_to_add,
                'amount_from_unallocated': amount_from_bot,
                'amount_fresh': amount_fresh
            })

        elif amount < 0:
            # Una cantidad negativa indica que estamos retirando capital
            withdraw_amount = abs(amount)

            # Verificacion de disponibilidad
            if bot_asset.qty_open > 0:
                if bot_asset.cap_to_add < withdraw_amount:
                    return Response({'error': 'Debe cerrar posiciones para retirar ese capital'}, status=400)
            else:
                # qty_open == 0, se puede disponer de cap_to_add y cap_to_trade
                if (bot_asset.cap_to_add + bot_asset.cap_to_trade) < withdraw_amount:
                    return Response({'error': 'Capital insuficiente para retirar'}, status=400)

            # Restar el capital
            from_add = min(withdraw_amount, bot_asset.cap_to_add)
            bot_asset.cap_to_add -= from_add
            remaining = withdraw_amount - from_add
            
            if remaining > 0:
                bot_asset.cap_to_trade -= remaining

            # Actualizar withdrawn y cap_no_asignado del Bot
            bot_asset.capWithdrew += withdraw_amount
            bot.cap_no_asignado += withdraw_amount
            
            bot_asset.save()
            bot.save()

            # Transaccion única para retiro interno
            Transaction.objects.create(
                bot=bot,
                assetbot=bot_asset,
                capital=withdraw_amount,
                add_withdraw=0, # Retiro
                move_between_bots=True,
                previous_capital_added=previous_capital_added,
                posterior_capital_added=previous_capital_added, # No cambia el total del sistema
                broker=bot_asset.broker,
                date=today
            )

            return Response({
                'message': 'Capital moved to unallocated successfully',
                'bot_asset_id': bot_asset.id,
                'withdraw_amount': withdraw_amount,
                'new_cap_to_add': bot_asset.cap_to_add,
                'new_cap_to_trade': bot_asset.cap_to_trade
            })

        else:
            return Response({'error': 'Amount cannot be zero'}, status=400)

class LoginView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        user = authenticate(username=username, password=password)
        
        if user:
            if user.is_superuser:
                token, created = Token.objects.get_or_create(user=user)
                return Response({'token': token.key})
            else:
                return Response({'error': 'Only superusers are allowed'}, status=status.HTTP_403_FORBIDDEN)
        else:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

class VerifyTokenView(APIView):
    permission_classes = [IsSuperUser]

    def get(self, request):
        return Response({'message': 'Token is valid', 'user': request.user.username})

class PortfolioHistoryView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        bot_id = request.query_params.get('bot_id')
        queryset = PortfolioHistory.objects.all().order_by('date')
        
        if bot_id:
            queryset = queryset.filter(bot_id=bot_id)
        else:
            queryset = queryset.filter(bot__isnull=True)
            
        data = []
        for record in queryset:
            data.append({
                'date': record.date,
                'capital': record.capital,
                'log_cum_sum': record.log_cum_sum,
                'ret_cums': record.ret_cums,
                'cagr': record.cagr,
                'spy_price': record.spy_price,
                'spy_ret': record.spy_ret,
                'spy_log_cum_sum': record.spy_log_cum_sum,
                'qqq_price': record.qqq_price,
                'qqq_ret': record.qqq_ret,
                'qqq_log_cum_sum': record.qqq_log_cum_sum,
            })
            
        return Response(data)

class ClosePositionView(APIView):
    permission_classes = [IsSuperUser]

    def post(self, request):
        bot_asset_id = request.data.get('bot_asset_id')
        all_quantity = request.data.get('all_quantity', False)
        execution_price = float(request.data.get('execution_price', 0))
        quantity_closed = float(request.data.get('quantity_closed', 0))
        try:
            bot_asset = BotAsset.objects.select_related('bot', 'broker').get(id=bot_asset_id)
        except BotAsset.DoesNotExist:
            return Response({'error': 'BotAsset not found'}, status=404)
        bot = bot_asset.bot
        broker = bot_asset.broker
        op_price = bot_asset.op_price
        qty_open = bot_asset.qty_open
        coms_per_trade = broker.coms
        today = timezone.now().date()

        if all_quantity:
            delta_pnl = qty_open*execution_price - bot_asset.cap_to_trade  - coms_per_trade
            new_pnl_un = 0
            new_op_price = execution_price
            new_trades = bot_asset.trades + 0.5
            new_coms = bot_asset.coms + coms_per_trade
            new_position = 0
            new_qty_open = 0
            new_cap_to_trade = 0
            new_cap_value_in_trade = 0
            new_cap_to_add = bot_asset.cap_to_add + qty_open*execution_price - coms_per_trade
        
        else:
            if quantity_closed > qty_open:
                return Response({'error': 'Quantity closed cannot be greater than open quantity'}, status=400)
            
            delta_pnl = (quantity_closed * (execution_price - op_price) - coms_per_trade)
            new_pnl_un = (qty_open-quantity_closed)*(bot_asset.last_price - op_price)
            new_op_price = bot_asset.op_price
            new_coms = bot_asset.coms + broker.coms
            new_position = bot_asset.position
            new_trades = bot_asset.trades
            new_qty_open = qty_open-quantity_closed
            new_cap_to_trade = new_op_price*(qty_open-quantity_closed) - coms_per_trade
            new_cap_value_in_trade = (qty_open-quantity_closed)*execution_price
            new_cap_to_add = bot_asset.cap_to_add + quantity_closed*execution_price - coms_per_trade
        
        bot_asset.position = new_position
        bot_asset.qty_open = new_qty_open
        bot_asset.cap_to_trade = new_cap_to_trade
        bot_asset.cap_value_in_trade = new_cap_value_in_trade
        bot_asset.op_price = new_op_price
        bot_asset.pnl_un = new_pnl_un
        bot_asset.PNL = bot_asset.PNL + delta_pnl
        bot_asset.trades = new_trades
        bot_asset.coms = new_coms
        bot_asset.cap_to_add = new_cap_to_add
        bot_asset.updated_date = today
        bot_asset.save()

        return Response({
            'message': 'Position closed successfully',
            'bot_asset_id': bot_asset.id,
            'capital_to_add': new_cap_to_add,
            'pnl_added': delta_pnl
        })

class PortfolioPercentagesView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        # Using aggregation to get totals, matching BotAssetAggregatedView logic
        asset_aggs = BotAsset.objects.aggregate(
            cap_to_add_sum=Sum('cap_to_add'),
            cap_value_in_trade_sum=Sum('cap_value_in_trade', filter=~Q(qty_open=0)),
            cap_to_trade_sum=Sum('cap_to_trade', filter=Q(qty_open=0)),
        )
        bot_aggs = Bot.objects.aggregate(
            cap_no_asignado_sum=Sum('cap_no_asignado')
        )

        cap_to_add_sum = asset_aggs['cap_to_add_sum'] or 0.0
        cap_value_in_trade_sum = asset_aggs['cap_value_in_trade_sum'] or 0.0
        cap_to_trade_sum = asset_aggs['cap_to_trade_sum'] or 0.0
        cap_no_asignado_sum = bot_aggs['cap_no_asignado_sum'] or 0.0

        total_portfolio_value = cap_value_in_trade_sum + cap_no_asignado_sum + cap_to_trade_sum + cap_to_add_sum

        if total_portfolio_value == 0:
            return Response({'error': 'Total portfolio value is zero'}, status=400)

        asset_bots = BotAsset.objects.select_related('bot').all()
        bots = Bot.objects.all()

        asset_bot_percentages = []
        bot_values = {bot.id: {'bot_name': bot.name, 'value': bot.cap_no_asignado or 0.0, 'cash': bot.cap_no_asignado or 0.0} for bot in bots}

        for asset in asset_bots:
            # If qty_open != 0, use cap_value_in_trade, else use cap_to_trade
            if asset.qty_open != 0:
                val = (asset.cap_value_in_trade or 0.0) + (asset.cap_to_add or 0.0)
            else:
                val = (asset.cap_to_trade or 0.0) + (asset.cap_to_add or 0.0)
            
            asset_bot_percentages.append({
                'bot_asset_id': asset.id,
                'asset': asset.asset,
                'bot_name': asset.bot.name,
                'value': val,
                'percentage': (val / total_portfolio_value) * 100
            })
            
            if asset.bot_id in bot_values:
                bot_values[asset.bot_id]['value'] += val
        
        # Add global cash to asset_bot_percentages
        asset_bot_percentages.append({
            'bot_asset_id': None,
            'asset': 'Cash',
            'bot_name': 'All',
            'value': cap_no_asignado_sum,
            'percentage': (cap_no_asignado_sum / total_portfolio_value) * 100
        })

        # Calculate bot percentages
        bot_percentages = []
        for bot_id, data in bot_values.items():
            bot_percentages.append({
                'bot_id': bot_id,
                'bot_name': data['bot_name'],
                'value': data['value'],
                'cash_included': data['cash'],
                'percentage': (data['value'] / total_portfolio_value) * 100
            })

        return Response({
            'total_portfolio_value': total_portfolio_value,
            'asset_bot_percentages': asset_bot_percentages,
            'bot_percentages': bot_percentages
        })
