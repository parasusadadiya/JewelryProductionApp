from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    send_from_directory
)

from werkzeug.utils import secure_filename

from pathlib import Path
from datetime import date, datetime
import sqlite3
import uuid


app = Flask(__name__)


BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "database" / "production.db"
UPLOAD_FOLDER = BASE_DIR / "photos"

UPLOAD_FOLDER.mkdir(exist_ok=True)


def get_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    return connection


def get_workflow(order_type):

    if order_type == "Repair":

        return [
            "Stone",
            "Components",
            "Setting / Jewelry Work",
            "OC",
            "Finish"
        ]

    return [
        "CAD",
        "Casting",
        "Stone",
        "Components",
        "Setting / Jewelry Work",
        "OC",
        "Finish"
    ]


@app.route("/photos/<filename>")
def serve_photo(filename):

    return send_from_directory(
        UPLOAD_FOLDER,
        filename
    )

@app.route("/photos/invoices/<filename>")
def serve_invoice(filename):

    return send_from_directory(
        UPLOAD_FOLDER / "invoices",
        filename
    )
@app.route("/photos/stone_photos/<filename>")
def serve_stone_photo(filename):

    return send_from_directory(
        UPLOAD_FOLDER / "stone_photos",
        filename
    )
@app.route("/")
def home():

    connection = get_connection()

    counts = {}

    stages = [
        "CAD",
        "Casting",
        "Stone",
        "Components",
        "Setting / Jewelry Work",
        "OC",
        "Finish"
    ]

    for stage in stages:

        result = connection.execute(
            """
            SELECT COUNT(*) AS count
            FROM production_stages
            WHERE stage_name = ?
            AND status != 'Completed'
            """,
            (stage,)
        ).fetchone()

        counts[stage] = result["count"]


    result = connection.execute(
        "SELECT COUNT(*) AS count FROM orders"
    ).fetchone()

    counts["New Orders"] = result["count"]


    # Order status counts

    result = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM orders
        WHERE NOT EXISTS (
            SELECT 1
            FROM production_stages
            WHERE production_stages.order_id = orders.id
            AND production_stages.status IN ('In Progress', 'Completed')
        )
        """
    ).fetchone()

    counts["Not Started Orders"] = result["count"]


    result = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM orders
        WHERE EXISTS (
            SELECT 1
            FROM production_stages
            WHERE production_stages.order_id = orders.id
            AND production_stages.status = 'In Progress'
        )
        """
    ).fetchone()

    counts["In Progress Orders"] = result["count"]


    result = connection.execute(
        """
        SELECT COUNT(*) AS count
        FROM orders
        WHERE EXISTS (
            SELECT 1
            FROM production_stages
            WHERE production_stages.order_id = orders.id
        )
        AND NOT EXISTS (
            SELECT 1
            FROM production_stages
            WHERE production_stages.order_id = orders.id
            AND production_stages.status != 'Completed'
        )
        """
    ).fetchone()

    counts["Finished Orders"] = result["count"]

    # Automatically archive completed To-Do items
    # after 4 days.

    connection.execute(
        """
        UPDATE todos
        SET
            archived = 1,
            archived_at = datetime('now')
        WHERE completed = 1
        AND archived = 0
        AND completed_at IS NOT NULL
        AND completed_at <= datetime('now', '-4 days')
        """
    )

    connection.commit()

      # Active To-Do items, sorted by due date

    todos = connection.execute(
        """
        SELECT
            id,
            task,
            due_date,
            notes
        FROM todos
WHERE completed = 0
AND archived = 0
ORDER BY due_date ASC, id ASC        """
    ).fetchall()


    # Completed To-Do items, newest completion first

    completed_todos = connection.execute(
        """
        SELECT
            id,
            task,
            due_date,
            notes,
            completed_at
        FROM todos
WHERE completed = 1
AND archived = 0
ORDER BY completed_at DESC, id DESC
        """
    ).fetchall()


    connection.close()

    return render_template(
        "dashboard.html",
        counts=counts,
        todos=todos,
        completed_todos=completed_todos
    )

@app.route("/orders/new")
def new_order():

    return render_template(
        "create_order.html"
    )

@app.route("/orders")
def orders():

    connection = get_connection()

    stage_filter = request.args.get("stage", "").strip()
    order_filter = request.args.get("filter", "").strip()

    base_query = """
        SELECT
            orders.*,
            customers.name AS customer_name
        FROM orders
        JOIN customers
            ON customers.id = orders.customer_id
    """

    params = []

    if stage_filter:

        base_query += """
            WHERE EXISTS (
                SELECT 1
                FROM production_stages
                WHERE production_stages.order_id = orders.id
                AND production_stages.stage_name = ?
                AND production_stages.status != 'Completed'
            )
        """

        params.append(stage_filter)

    elif order_filter == "in_progress":

        base_query += """
            WHERE EXISTS (
                SELECT 1
                FROM production_stages
                WHERE production_stages.order_id = orders.id
                AND production_stages.status = 'In Progress'
            )
        """

    elif order_filter == "not_started":

        base_query += """
            WHERE NOT EXISTS (
                SELECT 1
                FROM production_stages
                WHERE production_stages.order_id = orders.id
                AND production_stages.status IN ('In Progress', 'Completed')
            )
        """

    elif order_filter == "finished":

        base_query += """
            WHERE EXISTS (
                SELECT 1
                FROM production_stages
                WHERE production_stages.order_id = orders.id
            )
            AND NOT EXISTS (
                SELECT 1
                FROM production_stages
                WHERE production_stages.order_id = orders.id
                AND production_stages.status != 'Completed'
            )
        """

    else:

        base_query += """
            ORDER BY orders.id DESC
        """

    if stage_filter or order_filter in ("in_progress", "finished"):

        base_query += """
            ORDER BY orders.id DESC
        """

    orders = connection.execute(
        base_query,
        params
    ).fetchall()

    connection.close()

    return render_template(
        "orders.html",
        orders=orders
    )

@app.route("/orders/create", methods=["POST"])
def create_order():

    customer_name = request.form.get(
        "customer",
        ""
    ).strip()

    order_type = request.form.get(
        "order_type",
        "New"
    )

    product_number = request.form.get(
        "product_number",
        ""
    ).strip()

    quantity = request.form.get(
        "quantity",
        "1"
    )

    due_date = request.form.get(
        "due_date",
        ""
    )

    notes = request.form.get(
        "notes",
        ""
    ).strip()


    if not customer_name:

        return (
            "Customer name is required",
            400
        )


    try:

        quantity = int(quantity)

    except ValueError:

        quantity = 1


    connection = get_connection()


    customer = connection.execute(
        """
        SELECT id
        FROM customers
        WHERE name = ?
        """,
        (customer_name,)
    ).fetchone()


    if customer:

        customer_id = customer["id"]

    else:

        cursor = connection.execute(
            """
            INSERT INTO customers (name)
            VALUES (?)
            """,
            (customer_name,)
        )

        customer_id = cursor.lastrowid


    order_number = (
        "J-"
        + uuid.uuid4().hex[:8].upper()
    )


    photo_path = None

    photo = request.files.get("photo")


    if photo and photo.filename:

        extension = (
            Path(photo.filename)
            .suffix
            .lower()
        )


        allowed_extensions = [
            ".jpg",
            ".jpeg",
            ".png",
            ".webp"
        ]


        if extension in allowed_extensions:

            filename = (
                order_number
                + "_"
                + uuid.uuid4().hex[:6]
                + extension
            )


            photo.save(
                UPLOAD_FOLDER / filename
            )


            photo_path = (
                "/photos/"
                + filename
            )


    cursor = connection.execute(
        """
        INSERT INTO orders (
            order_number,
            customer_id,
            order_type,
            product_number,
            quantity,
            order_date,
            due_date,
            photo_path,
            notes,
            current_stage,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            order_number,
            customer_id,
            order_type,
            product_number,
            quantity,
            date.today().isoformat(),
            due_date,
            photo_path,
            notes,
            "Customer Order",
            "Pending"
        )
    )


    order_id = cursor.lastrowid


    workflow = get_workflow(
        order_type
    )


    for stage in workflow:

        connection.execute(
            """
            INSERT INTO production_stages (
                order_id,
                stage_name,
                status
            )
            VALUES (?, ?, ?)
            """,
            (
                order_id,
                stage,
                "Pending"
            )
        )


    connection.commit()
    connection.close()


    return redirect(
        url_for(
            "order_details",
            order_id=order_id
        )
    )


@app.route("/orders/<int:order_id>")
def order_details(order_id):

    connection = get_connection()

    order = connection.execute(
        """
        SELECT
            orders.*,
            customers.name AS customer_name
        FROM orders
        JOIN customers
            ON customers.id = orders.customer_id
        WHERE orders.id = ?
        """,
        (order_id,)
    ).fetchone()

    if not order:

        connection.close()

        return (
            "Order not found",
            404
        )

    stages = connection.execute(
        """
        SELECT *
        FROM production_stages
        WHERE order_id = ?
        ORDER BY id
        """,
        (order_id,)
    ).fetchall()

    stone_transactions = connection.execute(
        """
        SELECT *
        FROM stone_transactions
        WHERE order_id = ?
        ORDER BY id DESC
        """,
        (order_id,)
    ).fetchall()

    connection.close()

    return render_template(
        "order_details.html",
        order=order,
        stages=stages,
        stone_transactions=stone_transactions
    )

@app.route(
    "/orders/<int:order_id>/stones/<int:transaction_id>/invoice",
    methods=["POST"]
)
def attach_stone_invoice(order_id, transaction_id):

    invoice_file = request.files.get("invoice")

    if invoice_file and invoice_file.filename:

        filename = secure_filename(
            invoice_file.filename
        )

        if filename:

            invoice_filename = (
                f"invoice_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_"
                f"{filename}"
            )

            invoice_folder = (
                UPLOAD_FOLDER / "invoices"
            )

            invoice_folder.mkdir(
                parents=True,
                exist_ok=True
            )

            invoice_file.save(
                invoice_folder / invoice_filename
            )

            invoice_path = (
                f"/photos/invoices/{invoice_filename}"
            )

            connection = get_connection()

            connection.execute(
                """
                UPDATE stone_transactions
                SET invoice_path = ?
                WHERE id = ?
                AND order_id = ?
                """,
                (
                    invoice_path,
                    transaction_id,
                    order_id
                )
            )

            connection.commit()
            connection.close()

    return redirect(
        f"/orders/{order_id}"
    )
@app.route(
    "/orders/<int:order_id>/stones/create",
    methods=["POST"]
)
@app.route(
    "/orders/<int:order_id>/stones/create",
    methods=["POST"]
)
def create_stone_transaction(order_id):

    transaction_type = request.form.get(
        "transaction_type",
        ""
    ).strip()

    stone_description = request.form.get(
        "stone_description",
        ""
    ).strip()

    vendor_name = request.form.get(
        "vendor_name",
        ""
    ).strip()

    quantity = request.form.get(
        "quantity",
        ""
    ).strip()

    carat = request.form.get(
        "carat",
        ""
    ).strip()

    pickup_date = request.form.get(
        "pickup_date",
        ""
    ).strip()

    transaction_date = request.form.get(
        "transaction_date",
        ""
    ).strip()

    reason = request.form.get(
        "reason",
        ""
    ).strip()

    notes = request.form.get(
        "notes",
        ""
    ).strip()

    invoice_path = None

    invoice_file = request.files.get("invoice")

    if invoice_file and invoice_file.filename:

        filename = secure_filename(
            invoice_file.filename
        )

        if filename:

            invoice_filename = (
                f"invoice_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_"
                f"{filename}"
            )

            invoice_folder = (
                UPLOAD_FOLDER / "invoices"
            )

            invoice_folder.mkdir(
                parents=True,
                exist_ok=True
            )

            invoice_file.save(
                invoice_folder / invoice_filename
            )

            invoice_path = (
                f"/photos/invoices/{invoice_filename}"
            )

    photo_path = None

    stone_photo = request.files.get("stone_photo")

    if stone_photo and stone_photo.filename:

        filename = secure_filename(
            stone_photo.filename
        )

        if filename:

            photo_filename = (
                f"stone_{datetime.now().strftime('%Y%m%d%H%M%S%f')}_"
                f"{filename}"
            )

            photo_folder = (
                UPLOAD_FOLDER / "stone_photos"
            )

            photo_folder.mkdir(
                parents=True,
                exist_ok=True
            )

            stone_photo.save(
                photo_folder / photo_filename
            )

            photo_path = (
                f"/photos/stone_photos/{photo_filename}"
            )

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO stone_transactions (
            order_id,
            transaction_type,
            stone_description,
            vendor_name,
            quantity,
            carat,
            transaction_date,
            pickup_date,
            invoice_path,
            photo_path,
            reason,
            notes,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
        """,
        (
            order_id,
            transaction_type,
            stone_description,
            vendor_name,
            float(quantity) if quantity else None,
            float(carat) if carat else None,
            transaction_date or datetime.now().strftime("%Y-%m-%d"),
            pickup_date,
            invoice_path,
            photo_path,
            reason,
            notes
        )
    )

    connection.commit()
    connection.close()

    return redirect(
        f"/orders/{order_id}"
    )
@app.route(
    "/orders/<int:order_id>/stages/<int:stage_id>/start",
    methods=["POST"]
)
def start_stage(
    order_id,
    stage_id
):

    connection = get_connection()


    stage = connection.execute(
        """
        SELECT *
        FROM production_stages
        WHERE id = ?
        AND order_id = ?
        """,
        (
            stage_id,
            order_id
        )
    ).fetchone()


    if not stage:

        connection.close()

        return (
            "Production stage not found",
            404
        )


    now = datetime.now().isoformat(
        timespec="seconds"
    )


    connection.execute(
        """
        UPDATE production_stages
        SET
            status = 'In Progress',
            started_at = ?
        WHERE id = ?
        """,
        (
            now,
            stage_id
        )
    )


    connection.execute(
        """
        UPDATE orders
        SET
            current_stage = ?,
            status = 'In Progress'
        WHERE id = ?
        """,
        (
            stage["stage_name"],
            order_id
        )
    )


    connection.commit()
    connection.close()


    return redirect(
        url_for(
            "order_details",
            order_id=order_id
        )
    )


@app.route(
    "/orders/<int:order_id>/stages/<int:stage_id>/complete",
    methods=["POST"]
)
def complete_stage(
    order_id,
    stage_id
):

    connection = get_connection()


    stage = connection.execute(
        """
        SELECT *
        FROM production_stages
        WHERE id = ?
        AND order_id = ?
        """,
        (
            stage_id,
            order_id
        )
    ).fetchone()


    if not stage:

        connection.close()

        return (
            "Production stage not found",
            404
        )


    now = datetime.now().isoformat(
        timespec="seconds"
    )


    connection.execute(
        """
        UPDATE production_stages
        SET
            status = 'Completed',
            completed_at = ?
        WHERE id = ?
        """,
        (
            now,
            stage_id
        )
    )


    next_stage = connection.execute(
        """
        SELECT *
        FROM production_stages
        WHERE order_id = ?
        AND status != 'Completed'
        ORDER BY id
        LIMIT 1
        """,
        (order_id,)
    ).fetchone()


    if next_stage:

        connection.execute(
            """
            UPDATE orders
            SET
                current_stage = ?,
                status = 'In Progress'
            WHERE id = ?
            """,
            (
                next_stage["stage_name"],
                order_id
            )
        )

    else:

        connection.execute(
            """
            UPDATE orders
            SET
                current_stage = 'Finish',
                status = 'Completed'
            WHERE id = ?
            """,
            (order_id,)
        )


    connection.commit()
    connection.close()


    return redirect(
        url_for(
            "order_details",
            order_id=order_id
        )
    )


@app.route(
    "/orders/<int:order_id>/stages/<int:stage_id>/notes",
    methods=["POST"]
)
def save_stage_notes(
    order_id,
    stage_id
):

    notes = request.form.get(
        "notes",
        ""
    ).strip()


    connection = get_connection()


    connection.execute(
        """
        UPDATE production_stages
        SET notes = ?
        WHERE id = ?
        AND order_id = ?
        """,
        (
            notes,
            stage_id,
            order_id
        )
    )


    connection.commit()
    connection.close()


    return redirect(
        url_for(
            "order_details",
            order_id=order_id
        )
    )



@app.route("/todos/create", methods=["POST"])
def create_todo():

    task = request.form.get(
        "task",
        ""
    ).strip()

    due_date = request.form.get(
        "due_date",
        ""
    ).strip()

    notes = request.form.get(
        "notes",
        ""
    ).strip()


    if not task or not due_date:

        return redirect(
            url_for("home")
        )


    connection = get_connection()


    connection.execute(
        """
        INSERT INTO todos (
            task,
            due_date,
            notes,
            completed,
            created_at
        )
        VALUES (?, ?, ?, 0, datetime('now'))
        """,
        (
            task,
            due_date,
            notes
        )
    )


    connection.commit()
    connection.close()


    return redirect(
        url_for("home")
    )


@app.route(
    "/todos/<int:todo_id>/complete",
    methods=["POST"]
)
def complete_todo(todo_id):

    connection = get_connection()

    connection.execute(
        """
        UPDATE todos
        SET
            completed = 1,
            completed_at = datetime('now')
        WHERE id = ?
        """,
        (todo_id,)
    )

    connection.commit()
    connection.close()

    return redirect(
        url_for("home")
    )
@app.route(
    "/todos/<int:todo_id>/pending",
    methods=["POST"]
)
def pending_todo(todo_id):

    connection = get_connection()

    connection.execute(
        """
        UPDATE todos
        SET
            completed = 0,
            completed_at = NULL
        WHERE id = ?
        """,
        (todo_id,)
    )

    connection.commit()
    connection.close()

    return redirect(
        url_for("home")
    )

@app.route(
    "/todos/<int:todo_id>/archive",
    methods=["POST"]
)
def archive_todo(todo_id):

    connection = get_connection()

    connection.execute(
        """
        UPDATE todos
        SET
            archived = 1,
            archived_at = datetime('now')
        WHERE id = ?
        AND completed = 1
        AND archived = 0
        """,
        (todo_id,)
    )

    connection.commit()
    connection.close()

    return redirect(
        url_for("home")
    )

@app.route(
    "/todos/<int:todo_id>/edit",
    methods=["POST"]
)
def edit_todo(todo_id):

    task = request.form.get(
        "task",
        ""
    ).strip()

    due_date = request.form.get(
        "due_date",
        ""
    ).strip()

    notes = request.form.get(
        "notes",
        ""
    ).strip()


    if not task or not due_date:

        return redirect(
            url_for("home")
        )


    connection = get_connection()


    connection.execute(
        """
        UPDATE todos
        SET
            task = ?,
            due_date = ?,
            notes = ?
        WHERE id = ?
        AND completed = 0
        """,
        (
            task,
            due_date,
            notes,
            todo_id
        )
    )


    connection.commit()
    connection.close()


    return redirect(
        url_for("home")
    )
@app.route("/todos/archived")
def archived_todos():

    connection = get_connection()

    archived_todos = connection.execute(
        """
        SELECT
            id,
            task,
            due_date,
            notes,
            completed_at,
            archived_at
        FROM todos
        WHERE archived = 1
        ORDER BY archived_at DESC, id DESC
        """
    ).fetchall()

    connection.close()

    return render_template(
        "archived_todos.html",
        archived_todos=archived_todos
    )
@app.route(
    "/todos/<int:todo_id>/restore",
    methods=["POST"]
)
def restore_todo(todo_id):

    connection = get_connection()

    connection.execute(
        """
        UPDATE todos
        SET
            archived = 0,
            archived_at = NULL
        WHERE id = ?
        AND archived = 1
        """,
        (todo_id,)
    )

    connection.commit()
    connection.close()

    return redirect(
        url_for("archived_todos")
    )

if __name__ == "__main__":

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )