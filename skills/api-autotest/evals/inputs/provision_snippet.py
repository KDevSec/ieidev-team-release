# 环境数据预置脚本（节选）—— 单点创建测试用受限账号 / 角色 / 部门

def provision(prov):
    # --- 部门 ---
    d_sub = prov.create_dept(dept_name="AT部门_子树")
    d_m1 = prov.create_dept(dept_name="AT部门_多集1")
    d_m2 = prov.create_dept(dept_name="AT部门_多集2")

    # --- 角色（权限点 + 数据范围变体）---
    r_no_list = prov.create_role(role_key="at_role_no_list", menu_ids=[], data_scope="1")
    r_list    = prov.create_role(role_key="at_role_list", menu_ids=MENU_LIST, data_scope="1")
    r_sub     = prov.create_role(role_key="at_role_full_subtree", menu_ids=MENU_FULL, data_scope="4")
    r_multi   = prov.create_role(role_key="at_role_full_multiset", menu_ids=MENU_FULL,
                                 data_scope="2", dept_ids=[d_m1, d_m2])

    # --- 用户（这是环境里真实存在的全部测试账号）---
    prov.create_user(username="user_no_list",   dept_id=100,   role_ids=[r_no_list])
    prov.create_user(username="user_no_create", dept_id=100,   role_ids=[r_list])
    prov.create_user(username="pladmin_subtree", dept_id=d_sub, role_ids=[r_sub])
    prov.create_user(username="pladmin_multiset", dept_id=d_m1, role_ids=[r_multi])
