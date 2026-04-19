# Documentación de la API - proftview

Esta API proporciona acceso a la configuración y datos de los bots de trading en el sistema.

**URL Base:** `/api/proftview/`

---

## 0. Autenticación (Authentication)

Todos los endpoints que implican **modificación de datos** (POST, PUT, DELETE, etc.) requieren que el usuario esté autenticado y sea un **Superusuario** de Django. Sin embargo, las vistas de **solo lectura** (GET) son públicas y no requieren token.

Se utiliza **Token Authentication** de Django Rest Framework para las operaciones protegidas.

### Cabecera de Autorización
Las peticiones protegidas deben incluir la siguiente cabecera HTTP:
`Authorization: Token <tu_token_aqui>`

### 0.1 Login (Obtener Token)
**Endpoint:** `POST /auth/login/`

Permite obtener un token de acceso proporcionando credenciales de superusuario.

**Cuerpo (JSON):**
- `username`: Nombre de usuario.
- `password`: Contraseña.

**Respuesta Exitosa (200 OK):**
```json
{
  "token": "9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
}
```

### 0.2 Verificar Token
**Endpoint:** `GET /auth/verify/` [PROTEGIDO]

Permite verificar si un token sigue siendo válido y si el usuario asociado tiene permisos de superusuario.

**Ejemplo de Llamado:**
```bash
curl -X GET http://localhost:8000/api/proftview/auth/verify/ \
     -H "Authorization: Token 9944b09199c62bcf9418ad846dd0e4bbdfc6ee4b"
```

**Respuesta Exitosa (200 OK):**
```json
{
  "message": "Token is valid",
  "user": "admin"
}
```

---

## 1. Familias (Families) [PÚBLICO - GET]

Las familias agrupan diferentes bots bajo una misma categoría o estrategia general.

Las familias agrupan diferentes bots bajo una misma categoría o estrategia general.

### Listar Familias
**Endpoint:** `GET /families/`

**Ejemplo de Llamado:**
```bash
curl -X GET http://localhost:8000/api/proftview/families/
```

**Ejemplo de Respuesta:**
```json
[
  {
    "id": 1,
    "name": "Speculator Family",
    "active": true,
    "folder": "speculator_bots"
  },
  {
    "id": 2,
    "name": "Market Maker Family",
    "active": true,
    "folder": "mm_bots"
  }
]
```

### Detalle de Familia
**Endpoint:** `GET /families/{id}/`

**Ejemplo de Llamado:**
```bash
curl -X GET http://localhost:8000/api/proftview/families/1/
```

**Ejemplo de Respuesta:**
```json
{
  "id": 1,
  "name": "Speculator Family",
  "active": true,
  "folder": "speculator_bots"
}
```

---

## 2. Bots

Representa la configuración individual de cada bot.

### Listar Bots
**Endpoint:** `GET /bots/`

**Ejemplo de Llamado:**
```bash
curl -X GET http://localhost:8000/api/proftview/bots/
```

**Ejemplo de Respuesta:**
```json
[
  {
    "id": 1,
    "family": 1,
    "name": "BitTrader Bot",
    "strategy_type": "OneStrategy",
    "folder": "bit_trader",
    "execute_minute": 55,
    "summer_operate_hour": 14,
    "winter_operate_hour": 13,
    "active": true,
    "capital_active": 5000.0,
    "cap_value": 5200.0,
    "cap_ingresado": 5000.0,
    "cap_no_asignado": 0.0,
    "cap_to_add": 0.0,
    "cap_retirado": 0.0,
    "pnl_real": 200.0,
    "pnl_unreal": 50.0,
    "rets": 0.04,
    "tg_key1": "XXXX",
    "tg_key2": "YYYY",
    "tp": 0.05,
    "sl": 0.02
  }
]
```

---

## 3. Brokers

Configuración de los intermediarios financieros (brokers) utilizados.

### Listar Brokers
**Endpoint:** `GET /brokers/`

**Ejemplo de Llamado:**
```bash
curl -X GET http://localhost:8000/api/proftview/brokers/
```

**Ejemplo de Respuesta:**
```json
[
  {
    "id": 1,
    "name": "Interactive Brokers",
    "coms": 1.0
  },
  {
    "id": 2,
    "name": "Binance",
    "coms": 0.1
  }
]
```

---

## 4. Activos del Bot (Bot Assets)

Información detallada sobre los activos en los que opera cada bot. Permite filtrado avanzado.

### Listar Activos
**Endpoint:** `GET /assets/`

**Parámetros de Consulta (Query Params):**
- `family`: (Opcional) ID de la familia.
- `bot`: (Opcional) ID del bot.
- `broker`: (Opcional) ID del broker.

**Ejemplo de Llamado (con filtros):**
```bash
curl -X GET "http://localhost:8000/api/proftview/assets/?family=1&bot=1"
```

**Ejemplo de Respuesta:**
```json
{
  "id": 1,
  "bot": 1,
  "bot_name": "BitTrader Bot",
  "family_name": "Speculator Family",
  "broker_name": "Binance",
  "operate": true,
  "asset": "BTC/USDT",
  "params1": "volatilidad_alta",
  "params2": null,
  "params3": null,
  "alloc": 0.5,
  "broker": 2,
  "position": 1,
  "qty_open": 0.05,
  "cap_to_trade": 2500.0,
  "cap_to_add": 0.0,
  "cap_value_in_trade": 2550.0,
  "op_price": 45000.0,
  "last_price": 51000.0,
  "pnl_un": 50.0,
  "capAdded": 0.0,
  "PNL": 200.0,
  "trades": 15.0,
  "coms": 5.0,
  "created_date": "2024-03-19",
  "updated_date": "2024-03-19",
  "stats1": { "win_rate": 0.65 },
  "stats2": null
}
```

### Agregación de Activos (Totales)
**Endpoint:** `GET /assets/aggregated/`

Devuelve una sumatoria (agregación) de los campos más importantes de los `BotAsset` filtrados, así como el capital no asignado (`cap_no_asignado`) del `Bot` o `Bots` involucrados, y el total del capital añadido (`capAdded` de `BotAsset` + `cap_no_asignado` de `Bot`).

**Parámetros de Consulta (Query Params):**
- `bot`: (Opcional) ID del bot.
- `broker`: (Opcional) ID del broker.
- `family`: (Opcional) ID de la familia.

**Ejemplo de Llamado:**
```bash
curl -X GET "http://localhost:8000/api/proftview/assets/aggregated/?family=1&bot=1"
```

**Ejemplo de Respuesta:**
```json
{
  "cap_to_add_sum": 0.0,
  "cap_value_in_trade_sum": 2550.0,
  "pnl_un_sum": 50.0,
  "PNL_sum": 200.0,
  "coms_sum": 5.0,
  "trades_sum": 15.0,
  "cap_to_trade_sum": 2500.0,
  "capAdded_sum": 1000.0,
  "cap_no_asignado": 0.0,
  "total_capital_added": 1000.0
}
```

### Adición/Retiro de Capital a Activo (BotAsset)
**Endpoint:** `POST /assets/add-remove-capital/` [PROTEGIDO]

Permite añadir o retirar capital de un `BotAsset`. Los movimientos de capital se gestionan internamente entre el activo y el capital no asignado (`cap_no_asignado`) del bot asociado.

**Cuerpo de la Petición (Request Body):**
- `bot_asset_id`: (Requerido) ID del BotAsset.
- `amount`: (Requerido) Cantidad de capital. 
    - **Positivo**: Adiciona capital al activo, priorizando el uso del `cap_no_asignado` del bot. Si el bot no tiene suficiente, el resto se registra como capital externo.
    - **Negativo**: Retira capital del activo y lo mueve al `cap_no_asignado` del bot. Requiere que no haya posiciones abiertas si se desea retirar del capital operativo (`cap_to_trade`).

**Ejemplo de Llamado (Depósito):**
```bash
curl -X POST http://localhost:8000/api/proftview/assets/add-remove-capital/ \
     -H "Content-Type: application/json" \
     -H "Authorization: Token <tu_token>" \
     -d '{"bot_asset_id": 1, "amount": 500.0}'
```

**Ejemplo de Respuesta (Depósito):**
```json
{
  "message": "Capital added successfully",
  "bot_asset_id": 1,
  "new_cap_to_add": 500.0,
  "amount_from_unallocated": 100.0,
  "amount_fresh": 400.0
}
```

**Ejemplo de Respuesta (Retiro):**
```json
{
  "message": "Capital moved to unallocated successfully",
  "bot_asset_id": 1,
  "withdraw_amount": 200.0,
  "new_cap_to_add": 0.0,
  "new_cap_to_trade": 800.0
}
```

### Adición de Capital (Unassigned)
**Endpoint:** `POST /bot/add-capital/` [PROTEGIDO]

Permite añadir capital al campo `cap_no_asignado` de un bot y registrar una transacción externa.

**Cuerpo de la Petición (Request Body):**
- `bot_id`: (Requerido) ID del bot.
- `amount`: (Requerido) Cantidad de capital a añadir.
- `broker_id`: (Requerido) ID del broker relacionado.

**Ejemplo de Respuesta:**
```json
{
  "message": "Capital added successfully",
  "bot_id": 1,
  "new_cap_no_asignado": 1000.0,
  "total_capital_added": 5000.0
}
```

### Cierre de Posición (Close Position)
**Endpoint:** `POST /assets/close-position/` [PROTEGIDO]

Permite cerrar una posición total o parcial de un activo, actualizando el PNL y moviendo el capital liberado al campo `cap_to_add` del activo.

**Cuerpo de la Petición (Request Body):**
- `bot_asset_id`: (Requerido) ID del BotAsset.
- `all_quantity`: (Requerido) Boolean. `true` para cerrar toda la posición.
- `execution_price`: (Requerido) Precio de ejecución del cierre.
- `quantity_closed`: (Opcional) Requerido solo si `all_quantity` es `false`.

**Ejemplo de Llamado:**
```bash
curl -X POST http://localhost:8000/api/proftview/assets/close-position/ \
     -H "Content-Type: application/json" \
     -H "Authorization: Token <tu_token>" \
     -d '{"bot_asset_id": 1, "all_quantity": true, "execution_price": 48000.0}'
```

**Ejemplo de Respuesta:**
```json
{
  "message": "Position closed successfully",
  "bot_asset_id": 1,
  "capital_to_add": 2500.0,
  "pnl_added": 150.0
}
```

---

## 5. Historial de Portafolio (Portfolio History) [PÚBLICO - GET]

Permite obtener la serie de tiempo del capital y rendimientos, tanto a nivel global como por bot individual. Ideal para graficar el crecimiento del portafolio.

### Listar Histórico
**Endpoint:** `GET /history/`

**Parámetros de Consulta (Query Params):**
- `bot_id`: (Opcional) ID del bot para filtrar la historia de ese bot específico. Si se omite, devuelve el historial **Global** (total del sistema).

**Ejemplo de Llamado (Global):**
```bash
curl -X GET http://localhost:8000/api/proftview/history/
```

**Ejemplo de Llamado (Por Bot):**
```bash
curl -X GET http://localhost:8000/api/proftview/history/?bot_id=1
```

**Ejemplo de Respuesta:**
```json
[
  {
    "date": "2024-03-27",
    "capital": 10000.0,
    "chg_log": 0.0,
    "log_cum_sum": 0.0,
    "ret_cums": 0.0,
    "cagr": 0.0,
    "spy_price": 520.48,
    "spy_ret": 0.0,
    "qqq_price": 445.62,
    "qqq_ret": 0.0
  },
  {
    "date": "2024-03-28",
    "capital": 10500.0,
    "chg_log": 0.04879,
    "log_cum_sum": 0.04879,
    "ret_cums": 5.0,
    "cagr": 182.5,
    "spy_price": 522.5,
    "spy_ret": 0.0038,
    "qqq_price": 448.2,
    "qqq_ret": 0.0057
  }
]
```

---

## 6. Porcentajes del Portafolio (Portfolio Percentages) [PÚBLICO - GET]

Calcula la distribución porcentual del capital total del portafolio, desglosado tanto por activos (`BotAsset`) como por bots (`Bot`).

### Obtener Porcentajes
**Endpoint:** `GET /portfolio-percentages/`

**Descripción del Cálculo:**
- **Valor por Activo:** Se calcula como `cap_value_in_trade + cap_to_add` si el activo tiene una posición abierta (`position != 0`), de lo contrario se usa `cap_to_trade + cap_to_add`.
- **Efectivo (Cash):** Se incluye un rubro especial que representa el capital no asignado (`cap_no_asignado`) acumulado de todos los bots.
- **Valor por Bot:** Es la sumatoria de los valores de sus activos más su propio capital no asignado.

**Ejemplo de Llamado:**
```bash
curl -X GET http://localhost:8000/api/proftview/portfolio-percentages/
```

**Ejemplo de Respuesta:**
```json
{
  "total_portfolio_value": 150000.0,
  "asset_bot_percentages": [
    {
      "bot_asset_id": 1,
      "asset": "BTC/USDT",
      "bot_name": "BitTrader",
      "value": 10000.0,
      "percentage": 6.66
    },
    {
      "bot_asset_id": null,
      "asset": "Cash",
      "bot_name": "All",
      "value": 20000.0,
      "percentage": 13.33
    }
  ],
  "bot_percentages": [
    {
      "bot_id": 1,
      "bot_name": "BitTrader",
      "value": 50000.0,
      "cash_included": 10000.0,
      "percentage": 33.33
    }
  ]
}
```
